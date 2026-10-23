#include "CrewClips.h"
#include "CrewMotion.h"

#include "CrewClipData.inl"

static_assert(CrewClipJointCount == CrewClips::MaxJoints, "CrewClipData.inl's joints");

namespace CrewClipsDetail
{
	/** Left and right swap when a clip plays mirrored. */
	constexpr int32 Mirror[CrewClips::MaxJoints] = { 0, 1, 2, 4, 3, 6, 5, 8, 7, 10, 9 };
	/** A standing clip on a seated sailor: the hips don't sway on a seat, and the trunk follows them less. */
	constexpr float SeatedFromStanding[CrewClips::MaxJoints] = { 0.3f, 0.7f, 0.8f, 1.f, 1.f, 1.f, 1.f, 1.f, 1.f, 1.f, 1.f };

	uint32 Next(uint32& R)
	{
		R ^= R << 13; R ^= R >> 17; R ^= R << 5;
		return R;
	}
	float Rand01(uint32& R) { return float(Next(R) & 0xffffff) / float(0x1000000); }

	float CatmullRom(float P0, float P1, float P2, float P3, float F)
	{
		return 0.5f * (2.f * P1 + (P2 - P0) * F + (2.f * P0 - 5.f * P1 + 4.f * P2 - P3) * F * F + (3.f * P1 - P0 - 3.f * P2 + P3) * F * F * F);
	}

	FQuat FromRotVec(const FVector& V)
	{
		const double A = V.Size();
		return A > 1e-9 ? FQuat(V / A, A) : FQuat::Identity;
	}
}

int32 CrewClips::Num() { return UE_ARRAY_COUNT(CrewClipTable); }
const FCrewClipInfo& CrewClips::Info(int32 Clip) { return CrewClipTable[Clip]; }
const FCrewClipOnset& CrewClips::Onset(int32 Index) { return CrewClipOnsets[Index]; }
float CrewClips::Duration(int32 Clip) { return float(CrewClipTable[Clip].Frames - 1) / CrewClipRate; }
float CrewClips::Rate() { return CrewClipRate; }
int32 CrewClips::NumJoints() { return CrewClipJointCount; }
FName CrewClips::JointName(int32 Joint) { return CrewClipJointNames[Joint]; }
float CrewClips::LimitDeg(int32 Joint) { return CrewClipLimitDeg[Joint]; }
float CrewClips::GazeLimitDeg(int32 Axis) { return CrewClipGazeLimitDeg[Axis]; }

void CrewClips::Sample(int32 Clip, float T, bool bMirror, FVector* Out, float& OutYaw, float& OutPitch)
{
	using namespace CrewClipsDetail;
	const FCrewClipInfo& C = CrewClipTable[Clip];
	const float X = FMath::Clamp(T * CrewClipRate, 0.f, float(C.Frames - 1));
	const int32 I = FMath::Min(FMath::FloorToInt(X), C.Frames - 2);
	const float F = X - I;
	const int16* Rows[4];
	for (int32 K = 0; K < 4; ++K) Rows[K] = CrewClipValues + C.Offset + FMath::Clamp(I - 1 + K, 0, C.Frames - 1) * CrewClipChannels;
	auto Channel = [&](int32 Ch)
	{
		return FMath::DegreesToRadians(0.01f * CatmullRom(Rows[0][Ch], Rows[1][Ch], Rows[2][Ch], Rows[3][Ch], F));
	};
	for (int32 J = 0; J < CrewClipJointCount; ++J)
	{
		const int32 Src = bMirror ? Mirror[J] : J;
		const FVector V(Channel(3 * Src), Channel(3 * Src + 1), Channel(3 * Src + 2));
		// Mirrored in the sailor's sagittal plane (Y -> -Y): a rotation vector, being axial, becomes (-x, y, -z).
		// (The bake keeps every frame inside the limit; the spline between frames can overshoot it by a hair.)
		Out[J] = (bMirror ? FVector(-V.X, V.Y, -V.Z) : V).GetClampedToMaxSize(FMath::DegreesToRadians(CrewClipLimitDeg[J]));
	}
	OutYaw = FMath::Clamp(FMath::RadiansToDegrees(Channel(CrewClipChannels - 2)), -CrewClipGazeLimitDeg[0], CrewClipGazeLimitDeg[0]) * (bMirror ? -1.f : 1.f);
	OutPitch = FMath::Clamp(FMath::RadiansToDegrees(Channel(CrewClipChannels - 1)), -CrewClipGazeLimitDeg[1], CrewClipGazeLimitDeg[1]);
}

float CrewClips::TrunkLean(const FVector* J, int32 Axis)
{
	using namespace CrewClipsDetail;
	const FVector Up = (FromRotVec(J[0]) * FromRotVec(J[1]) * FromRotVec(J[2])).RotateVector(FVector::UpVector);
	return FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(Axis == 0 ? Up.Y : Up.X, -1.0, 1.0)));
}

float CrewClipStanceWeight(ECrewStance Stance, float Hike)
{
	switch (Stance)
	{
	// Moving across, on the wire or righting: no idling.
	case ECrewStance::Crossing: case ECrewStance::Trapeze: case ECrewStance::Righting: return 0.f;
	// Hiked hard there is no slack for fidgeting.
	case ECrewStance::RailHike: return 1.f - 0.5f * FMath::Clamp(Hike, 0.f, 1.f);
	case ECrewStance::DinghyHike: return 0.7f - 0.4f * FMath::Clamp(Hike, 0.f, 1.f);
	// The helm's hands are on the tiller and the sheet: the trunk and gaze carry the idle.
	case ECrewStance::Helm: return 0.8f;
	default: return 1.f;
	}
}

namespace CrewClipsDetail
{
	/** A clip and start for the next idle: seated clips a little more often (every stance that idles is seated). */
	FCrewClipCursor Pick(uint32& Rng, int32 Avoid, int32 Avoid2 = -1)
	{
		float Total = 0.f;
		for (int32 C = 0; C < CrewClips::Num(); ++C) if (C != Avoid && C != Avoid2) Total += CrewClipTable[C].Kind == ECrewClipKind::Seated ? 1.5f : 1.f;
		float R = Rand01(Rng) * Total;
		FCrewClipCursor Out;
		for (int32 C = 0; C < CrewClips::Num(); ++C)
		{
			if (C == Avoid || C == Avoid2) continue;
			Out.Clip = C;
			R -= CrewClipTable[C].Kind == ECrewClipKind::Seated ? 1.5f : 1.f;
			if (R <= 0.f) break;
		}
		Out.T = Rand01(Rng) * FMath::Max(0.f, CrewClips::Duration(Out.Clip) - 3.f);
		Out.bMirror = Rand01(Rng) < 0.5f;
		// docs/crew-idle-variety/: a few seconds of it, not always all, and not always as much of it. Played whole at full
		// size, eight clips came round often enough to read as a loop (a sixth of a sailor's 4 s stretches matched one
		// they'd made before).
		Out.PlayFor = 3.f + 5.f * Rand01(Rng);
		Out.Amp = 0.75f + 0.25f * Rand01(Rng);
		Out.Pace = 0.9f + 0.2f * Rand01(Rng);
		return Out;
	}

	void SampleScaled(const FCrewClipCursor& C, FVector* Out, float& Yaw, float& Pitch)
	{
		CrewClips::Sample(C.Clip, C.T, C.bMirror, Out, Yaw, Pitch);
		for (int32 J = 0; J < CrewClipJointCount; ++J) Out[J] *= C.Amp;
		Yaw *= C.Amp;
		Pitch *= C.Amp;
		if (CrewClipTable[C.Clip].Kind == ECrewClipKind::Standing)
		{
			for (int32 J = 0; J < CrewClipJointCount; ++J) Out[J] *= SeatedFromStanding[J];
		}
	}

	/** The joints a cursor gives at a weight (the hiking dinghy sailor's pelvis held), within the limits. */
	void Weighted(const FCrewClipCursor& C, float Weight, float PelvisScale, FVector* Out, float& Yaw, float& Pitch)
	{
		SampleScaled(C, Out, Yaw, Pitch);
		for (int32 J = 0; J < CrewClipJointCount; ++J)
		{
			Out[J] = (Out[J] * (Weight * (J == 0 ? PelvisScale : 1.f))).GetClampedToMaxSize(FMath::DegreesToRadians(CrewClipLimitDeg[J]));
		}
	}

	void StartFade(FCrewClipState& S, const FCrewClipCursor& To, float Seconds)
	{
		S.Next = To;
		S.Blend = 0.f;
		S.BlendSeconds = Seconds;
	}
}

void CrewClipStep(FCrewClipState& S, const FCrewClipInput& In, float Dt)
{
	using namespace CrewClipsDetail;
	if (!S.bStarted)
	{
		S.Rng = (In.Seed * 2654435761u + 0x9e3779b9u) | 1u;
		for (int32 K = 0; K < 3; ++K) Next(S.Rng);
		// The sailor's pace, times a pick's (0.9..1.1): at most about 1.2 (at 1.3 the helm's planted foot slid 3.4 cm in
		// SailingSim.Visual.CrewClipLimits, past its 3).
		S.Rate = 0.85f + 0.25f * Rand01(S.Rng);
		S.Cur = Pick(S.Rng, -1);
		S.Blend = 1.f;
		for (int32 K = 0; K < 3; ++K) { S.TiltF[0][K] = In.Roll; S.TiltF[1][K] = In.Pitch; }
		S.bStarted = true;
	}
	Dt = FMath::Max(Dt, 0.f);
	// Quiet within a fifth of a second of a move; back over a second and a half once settled.
	const float StanceW = CrewClipStanceWeight(In.Stance, In.Hike);
	const bool bPlay = !In.bQuiet && StanceW > 0.f;
	S.Activity = bPlay ? FMath::Min(1.f, S.Activity + Dt / 1.5f) : FMath::Max(0.f, S.Activity - Dt / 0.2f);

	// The clips play on at the sailor's pace; at the end of a pick's few seconds, or as near the clip's end as the fade needs,
	// the next fades in, over 0.8 to 1.6 s.
	S.Cur.T += Dt * S.Rate * S.Cur.Pace;
	S.Cur.PlayFor -= Dt;
	if (S.Blend < 1.f)
	{
		S.Next.T += Dt * S.Rate * S.Next.Pace;
		S.Next.PlayFor -= Dt;
		S.Blend += Dt / FMath::Max(S.BlendSeconds, 0.05f);
		if (S.Blend >= 1.f) { S.Cur = S.Next; S.Blend = 1.f; }
	}
	const float Dur = CrewClips::Duration(S.Cur.Clip);
	if (S.Cur.T >= Dur) S.Cur.T = FMath::Fmod(S.Cur.T, Dur);
	if (S.Blend >= 1.f && (Dur - S.Cur.T < 1.6f * S.Rate * 1.1f || S.Cur.PlayFor <= 0.f))   // (the longest fade ends inside the clip)
	{
		const FCrewClipCursor To = Pick(S.Rng, S.Cur.Clip, S.Earlier);
		S.Earlier = S.Cur.Clip;
		StartFade(S, To, 0.8f + 0.8f * Rand01(S.Rng));
	}

	// The heel's slow trend (three 1 s lags: a puff heeling the boat over a few seconds, not the chop under it), as the
	// sailor feels it: sideways facing forward, fore and aft facing across the boat.
	const float A = 1.f - FMath::Exp(-Dt / 1.f);
	for (int32 Ax = 0; Ax < 2; ++Ax)
	{
		float* F = S.TiltF[Ax];
		const float Before = F[2];
		F[0] += ((Ax == 0 ? In.Roll : In.Pitch) - F[0]) * A;
		F[1] += (F[0] - F[1]) * A;
		F[2] += (F[1] - F[2]) * A;
		S.TiltTrend[Ax] = Dt > 0.f ? (F[2] - Before) / Dt : 0.f;
	}
	S.Cooldown = FMath::Max(0.f, S.Cooldown - Dt);
	// A change of heel: shift the weight against it (tipping right, toward the left; tipping forward, back), starting a
	// clip's own weight shift that way rather than leaning the trunk by rule, unless the clip is already moving or leaning
	// that way.
	const int32 Axis = FMath::Abs(S.TiltTrend[1]) > FMath::Abs(S.TiltTrend[0]) ? 1 : 0;
	const int32 Want = -int32(FMath::Sign(S.TiltTrend[Axis]));
	if (bPlay && S.Activity > 0.5f && S.Cooldown <= 0.f && S.Blend >= 1.f && FMath::Abs(S.TiltTrend[Axis]) > FMath::DegreesToRadians(1.2f)
		&& S.LeanRate[Axis] * Want <= 0.f && S.Lean[Axis] * Want < 2.f)
	{
		// A clip's onset on that axis, played the way round that leans as wanted (mirroring turns a sideways shift over),
		// from about where the trunk is now: one that starts behind it (so the crossfade doesn't lean it the wrong way
		// first), nearest it, among a few drawn at random.
		const float Weight = CrewMinJerk(S.Activity) * StanceW;
		const float PelvisScale = In.Stance == ECrewStance::DinghyHike ? 0.f : 1.f;
		TArray<FCrewClipCursor, TInlineAllocator<64>> Candidates;
		for (int32 C = 0; C < CrewClips::Num(); ++C)
		{
			const FCrewClipInfo& Info = CrewClipTable[C];
			for (int32 K = 0; K < Info.OnsetCount; ++K)
			{
				const FCrewClipOnset& O = CrewClipOnsets[Info.OnsetBegin + K];
				if (O.Axis != Axis || (Axis == 1 && O.Direction != Want)) continue;
				FCrewClipCursor To;
				To.Clip = C;
				To.T = O.Frame / CrewClipRate;
				To.bMirror = Axis == 0 ? O.Direction != Want : Rand01(S.Rng) < 0.5f;
				Candidates.Add(To);
			}
		}
		float Best = UE_BIG_NUMBER;
		FCrewClipCursor Chosen;
		for (int32 Draw = 0; Draw < 10 && Candidates.Num() > 0; ++Draw)
		{
			const FCrewClipCursor& To = Candidates[FMath::Min(int32(Rand01(S.Rng) * Candidates.Num()), Candidates.Num() - 1)];
			FVector J[CrewClips::MaxJoints];
			float Yaw, Pitch;
			Weighted(To, Weight, PelvisScale, J, Yaw, Pitch);
			const float Start = CrewClips::TrunkLean(J, Axis);
			FCrewClipCursor Later = To;
			Later.T = FMath::Min(To.T + 1.f, CrewClips::Duration(To.Clip));
			Weighted(Later, Weight, PelvisScale, J, Yaw, Pitch);
			const float Move = (CrewClips::TrunkLean(J, Axis) - Start) * Want;
			const float Ahead = (Start - S.Lean[Axis]) * Want;
			const float Cost = FMath::Abs(Ahead) + 4.f * FMath::Max(Ahead, 0.f) - Move;
			if (Cost < Best) { Best = Cost; Chosen = To; }
		}
		if (Chosen.Clip >= 0)
		{
			StartFade(S, Chosen, 0.35f);
			S.HeelShifts++;
			S.LastShiftDirection = Want;
			S.LastShiftAxis = Axis;
			S.Cooldown = 3.f;
		}
	}

	// The pose: the playing clip, crossfaded into the next, weighted and kept within each joint's limits.
	FVector Cur[CrewClips::MaxJoints], Nxt[CrewClips::MaxJoints];
	float Yaw, Pitch;
	SampleScaled(S.Cur, Cur, Yaw, Pitch);
	if (S.Blend < 1.f)
	{
		float YawN, PitchN;
		SampleScaled(S.Next, Nxt, YawN, PitchN);
		const float B = CrewMinJerk(S.Blend);
		for (int32 J = 0; J < CrewClipJointCount; ++J) Cur[J] = FMath::Lerp(Cur[J], Nxt[J], B);
		Yaw = FMath::Lerp(Yaw, YawN, B);
		Pitch = FMath::Lerp(Pitch, PitchN, B);
	}
	S.Weight = CrewMinJerk(S.Activity) * StanceW;
	// Hiking from the dinghy's straps the pelvis is wedged on the deck edge (and the feet's planting under the strap is
	// sensitive to it).
	const float PelvisScale = In.Stance == ECrewStance::DinghyHike ? 0.f : 1.f;
	for (int32 J = 0; J < CrewClipJointCount; ++J)
	{
		S.Joints[J] = (Cur[J] * (S.Weight * (J == 0 ? PelvisScale : 1.f))).GetClampedToMaxSize(FMath::DegreesToRadians(CrewClipLimitDeg[J]));
	}
	S.GazeYaw = FMath::Clamp(Yaw * S.Weight, -CrewClipGazeLimitDeg[0], CrewClipGazeLimitDeg[0]);
	S.GazePitch = FMath::Clamp(Pitch * S.Weight, -CrewClipGazeLimitDeg[1], CrewClipGazeLimitDeg[1]);
	for (int32 Ax = 0; Ax < 2; ++Ax)
	{
		const float Lean = CrewClips::TrunkLean(S.Joints, Ax);
		S.LeanRate[Ax] = Dt > 0.f ? (Lean - S.Lean[Ax]) / Dt : 0.f;
		S.Lean[Ax] = Lean;
	}
}
