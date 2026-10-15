#include "Wind.h"
#include "LakeTerrain.h"
#include <cstring>
#include <fstream>
#include <iterator>
#include <memory>

namespace Sailing
{
	namespace
	{
		uint64_t Mix(uint64_t X)
		{
			// splitmix64's finaliser: every input bit reaches every output bit.
			X += 0x9e3779b97f4a7c15ULL;
			X = (X ^ (X >> 30)) * 0xbf58476d1ce4e5b9ULL;
			X = (X ^ (X >> 27)) * 0x94d049bb133111ebULL;
			return X ^ (X >> 31);
		}
		uint64_t CellHash(int64_t I, int64_t J, int64_t G, uint32_t Seed)
		{
			return Mix(Mix(Mix(uint64_t(I) * 0x2545f4914f6cdd1dULL ^ Seed) ^ uint64_t(J)) ^ uint64_t(G) * 0x9e3779b97f4a7c15ULL);
		}
		/** The Nth uniform number in [0, 1) from a hash. */
		double U01(uint64_t H, int N) { return double(Mix(H + uint64_t(N) * 0x632be59bd9b4e019ULL) >> 11) * (1.0 / 9007199254740992.0); }

		/** Business-Dyer stability correction for momentum, psi_m(z/L). */
		double PsiM(double Zeta)
		{
			if (Zeta >= 0.0) return -5.0 * std::min(Zeta, 1.0);
			const double X = std::sqrt(std::sqrt(1.0 - 16.0 * Zeta));
			return 2.0 * std::log(0.5 * (1.0 + X)) + std::log(0.5 * (1.0 + X * X)) - 2.0 * std::atan(X) + 0.5 * kPi;
		}

		/** The puff layer's spread of 2-minute means (over the half-hour mean) per unit of its standard deviation, measured
		 *  with MeasureGustStats (fit_gusts.py's measure): converts the stations' puff strength to the field's. */
		constexpr double kPuffSlowRms = 0.83;

		/** The puff envelope at an age: lands, grows over Grow seconds, holds, fades over the last 45 % of its life. */
		double Envelope(double Age, double Grow, double Life)
		{
			return SmoothStep(0.0, Grow, Age) * (1.0 - SmoothStep(0.55 * Life, Life, Age));
		}

		std::shared_ptr<const FTurbulenceTile>& SharedTile()
		{
			static std::shared_ptr<const FTurbulenceTile> Tile;
			return Tile;
		}

		float HalfToFloat(uint16_t H)
		{
			const uint32_t Sign = uint32_t(H & 0x8000u) << 16;
			uint32_t Exp = (H >> 10) & 0x1Fu, Man = H & 0x3FFu, Bits;
			if (Exp == 0)
			{
				if (Man == 0) Bits = Sign;
				else
				{
					// Subnormal: normalise.
					Exp = 127 - 15 + 1;
					while ((Man & 0x400u) == 0) { Man <<= 1; --Exp; }
					Man &= 0x3FFu;
					Bits = Sign | (Exp << 23) | (Man << 13);
				}
			}
			else if (Exp == 31) Bits = Sign | 0x7F800000u | (Man << 13);
			else Bits = Sign | ((Exp + 127 - 15) << 23) | (Man << 13);
			float F;
			std::memcpy(&F, &Bits, 4);
			return F;
		}
	}

	// ---------------------------------------------------------------- the Mann tile

	void FTurbulenceTile::Sample(double X, double Y, double& OutU, double& OutV) const
	{
		const double FX = X / Dx, FY = Y / Dx;
		const double X0 = std::floor(FX), Y0 = std::floor(FY);
		const double TX = FX - X0, TY = FY - Y0;
		const int I0 = int(((int64_t(X0) % Nx) + Nx) % Nx), J0 = int(((int64_t(Y0) % Ny) + Ny) % Ny);
		const int I1 = I0 + 1 == Nx ? 0 : I0 + 1, J1 = J0 + 1 == Ny ? 0 : J0 + 1;
		const size_t A = size_t(J0) * Nx + I0, B = size_t(J0) * Nx + I1, C = size_t(J1) * Nx + I0, E = size_t(J1) * Nx + I1;
		OutU = Lerp(Lerp(U[A], U[B], TX), Lerp(U[C], U[E], TX), TY);
		OutV = Lerp(Lerp(V[A], V[B], TX), Lerp(V[C], V[E], TX), TY);
	}

	bool FTurbulenceTile::LoadSharedFromMemory(const uint8_t* Data, size_t Size)
	{
		if (!Data || Size < 32 || std::memcmp(Data, "MANN", 4) != 0) return false;
		uint32_t Version, NX, NY;
		float Dx, L, Gamma, Ratio;
		std::memcpy(&Version, Data + 4, 4);
		std::memcpy(&NX, Data + 8, 4);
		std::memcpy(&NY, Data + 12, 4);
		std::memcpy(&Dx, Data + 16, 4);
		std::memcpy(&L, Data + 20, 4);
		std::memcpy(&Gamma, Data + 24, 4);
		std::memcpy(&Ratio, Data + 28, 4);
		const size_t Count = size_t(NX) * NY;
		if (Version != 1 || NX == 0 || NY == 0 || NX > 4096 || NY > 4096 || Size < 32 + 4 * Count) return false;
		auto Tile = std::make_shared<FTurbulenceTile>();
		Tile->Nx = int(NX);
		Tile->Ny = int(NY);
		Tile->Dx = Dx;
		Tile->LengthScale = L;
		Tile->Gamma = Gamma;
		Tile->VRatio = Ratio;
		Tile->U.resize(Count);
		Tile->V.resize(Count);
		const uint8_t* P = Data + 32;
		for (size_t K = 0; K < Count; ++K) { uint16_t H; std::memcpy(&H, P + 2 * K, 2); Tile->U[K] = HalfToFloat(H); }
		P += 2 * Count;
		for (size_t K = 0; K < Count; ++K) { uint16_t H; std::memcpy(&H, P + 2 * K, 2); Tile->V[K] = HalfToFloat(H); }
		SharedTile() = std::move(Tile);
		return true;
	}

	bool FTurbulenceTile::LoadShared(const std::string& Path)
	{
		std::ifstream In(Path, std::ios::binary);
		if (!In) return false;
		const std::vector<uint8_t> Bytes((std::istreambuf_iterator<char>(In)), std::istreambuf_iterator<char>());
		return LoadSharedFromMemory(Bytes.data(), Bytes.size());
	}

	const FTurbulenceTile* FTurbulenceTile::Shared()
	{
		const std::shared_ptr<const FTurbulenceTile>& Tile = SharedTile();
		return Tile && Tile->IsValid() ? Tile.get() : nullptr;
	}

	// ---------------------------------------------------------------- frames

	void FDriftFrame::Reanchor(double T, double AnchorX, double AnchorY, double NewAngle, double NewVX, double NewVY)
	{
		// Nothing changed: leave the frame exactly as it is (a field updated every frame stays bit-identical at any rate).
		if (NewAngle == Angle && NewVX == VX && NewVY == VY) return;
		// Where the anchor sits in the pattern now; the new frame puts the same pattern point there.
		double Along, Across;
		Local(AnchorX, AnchorY, T, Along, Across);
		Angle = NewAngle;
		C = std::cos(NewAngle);
		S = std::sin(NewAngle);
		VX = NewVX;
		VY = NewVY;
		T0 = T;
		OX = AnchorX - (Along * C - Across * S);
		OY = AnchorY - (Along * S + Across * C);
	}

	// ---------------------------------------------------------------- the field

	FWindField::FWindField(const FWindParams& InParams)
	{
		SetParams(InParams);
	}

	double FGustFront::DistanceAhead(double X, double Y, double T) const
	{
		const double A = MoveDegrees * kDegToRad;
		const double Along = (X - StartX) * std::cos(A) + (Y - StartY) * std::sin(A);
		return Along - SpeedMs * (T - StartTime);
	}

	double FGustFront::AlongFront(double X, double Y) const
	{
		const double A = MoveDegrees * kDegToRad;
		return -(X - StartX) * std::sin(A) + (Y - StartY) * std::cos(A);
	}

	double FGustFront::Behind(double X, double Y, double T) const
	{
		if (!bActive || T < StartTime) return 0.0;
		const double W = SmoothStep(LeadingEdgeMeters, -LeadingEdgeMeters, DistanceAhead(X, Y, T));
		return W * (1.0 - SmoothStep(DecayStartTime, DecayStartTime + DecaySeconds, T));
	}

	double FGustFront::TemperatureDropAt(double X, double Y, double T) const
	{
		if (!bActive || T < StartTime || ColdPoolDeltaC <= 0.0) return 0.0;
		// The cold air arrives with the wind shift and stays: the pool lingers long after its outflow has eased (it warms
		// back over the following hour or so).
		const double In = SmoothStep(LeadingEdgeMeters, -2.0 * LeadingEdgeMeters, DistanceAhead(X, Y, T));
		return ColdPoolDeltaC * In * (1.0 - 0.6 * SmoothStep(DecayStartTime, DecayStartTime + 3600.0, T));
	}

	Vec3 FGustFront::BurstAt(double X, double Y, double Z, double T) const
	{
		if (!bActive || Burst.PeakOutflowMs <= 0.0 || T < BurstStartTime) return Vec3();
		const double Age = T - BurstStartTime;
		const double Life = SmoothStep(0.0, BurstGrowSeconds, Age) * (1.0 - SmoothStep(BurstGrowSeconds + BurstHoldSeconds,
			BurstGrowSeconds + BurstHoldSeconds + BurstDecaySeconds, Age));
		if (Life <= 0.0) return Vec3();
		// The centre rides in the rain core on the storm's axis, a fixed distance behind the front.
		const double A = MoveDegrees * kDegToRad;
		const double Travel = SpeedMs * (T - StartTime) - BurstBehindM;
		const double CX = StartX + std::cos(A) * Travel, CY = StartY + std::sin(A) * Travel;
		double U, V, W;
		Burst.At(X - CX, Y - CY, Z, U, V, W);
		return Vec3(U, V, W) * Life;
	}

	void FWindField::SetParamsAt(const FWindParams& InParams, double T, double AnchorX, double AnchorY)
	{
		const FDriftFrame OldPuffs = Puffs, OldAir = Air;
		Params = InParams;
		Derive();
		// Both patterns keep drifting from where they were; a new direction turns them about the anchor.
		Puffs = OldPuffs;
		Air = OldAir;
		const double Down = std::atan2(DownwindDir.Y, DownwindDir.X);
		const double Aloft = Down + (6.0 + 6.0 * Clamp(D.ZetaAt10 / 0.3, 0.0, 1.0)) * kDegToRad;
		const double Vp = MeanSpeed10 * D.AloftRatio;
		// The puffs' lanes lie along the surface wind and drift with the wind aloft, a few degrees across them: a point on
		// the water is crossed by lane after lane instead of sitting in one for good.
		Puffs.Reanchor(T, AnchorX, AnchorY, Down, std::cos(Aloft) * Vp, std::sin(Aloft) * Vp);
		Air.Reanchor(T, AnchorX, AnchorY, Down, DownwindDir.X * MeanSpeed10, DownwindDir.Y * MeanSpeed10);
	}

	void FWindField::SetParams(const FWindParams& InParams)
	{
		Params = InParams;
		Derive();
		const double Down = std::atan2(DownwindDir.Y, DownwindDir.X);
		const double Aloft = Down + (6.0 + 6.0 * Clamp(D.ZetaAt10 / 0.3, 0.0, 1.0)) * kDegToRad;
		const double Vp = MeanSpeed10 * D.AloftRatio;
		Puffs = FDriftFrame();
		Air = FDriftFrame();
		Puffs.Reanchor(0.0, 0.0, 0.0, Down, std::cos(Aloft) * Vp, std::sin(Aloft) * Vp);
		Air.Reanchor(0.0, 0.0, 0.0, Down, DownwindDir.X * MeanSpeed10, DownwindDir.Y * MeanSpeed10);
	}

	void FWindField::Derive()
	{
		MeanSpeed10 = Params.SpeedKnots * kKnot;
		const double From = Params.FromDegrees * kDegToRad;
		DownwindDir = Vec3(-std::cos(From), -std::sin(From), 0.0);

		// Deterministic phases from the seed (xorshift), so the shifts repeat exactly for a given seed.
		uint32_t S = Params.Seed ? Params.Seed : 1u;
		for (double& Phase : Phases)
		{
			S ^= S << 13; S ^= S >> 17; S ^= S << 5;
			Phase = (S % 100000u) / 100000.0 * 2.0 * kPi;
		}

		// Stability from the bulk Richardson number at 10 m (air minus water temperature over the wind squared), then
		// z/L by the usual surface-layer fits (Businger-Dyer). Zero difference is neutral: the plain log profile.
		const double U = std::max(MeanSpeed10, 0.5);
		const double Rb = kGravity * 10.0 * Params.AirMinusWaterC / (288.0 * U * U);
		double Zeta = 0.0;
		if (Rb < 0.0) Zeta = std::max(10.0 * Rb, -2.0);
		else if (Rb > 0.0) Zeta = std::min(10.0 * Rb / std::max(1.0 - 5.0 * Rb, 0.25), 1.0);
		D.ZetaAt10 = Zeta;
		ObukhovL = std::fabs(Zeta) > 1e-9 ? 10.0 / Zeta : 1e9;
		ProfileNorm = Profile(10.0);
		const double Unstable = Clamp(-Zeta / 0.5, 0.0, 1.0), Stable = Clamp(Zeta / 0.3, 0.0, 1.0);
		// The puffs come down from the wind aloft: faster than the surface wind, more so when the air is stable.
		D.AloftRatio = 1.25 + 0.25 * Stable - 0.1 * Unstable;

		// Sizes. Across: from the mixed layer (the downdraft footprint about 0.6 of its depth, the cells 1.3 footprints
		// apart) and from the calibrated time between puffs at a point at the drift speed; their geometric mean.
		const double Vp = std::max(MeanSpeed10 * D.AloftRatio, 0.5);
		D.Streets = SmoothStep(4.5, 8.5, U) * (1.0 - 0.5 * Stable);
		const double Elong = 1.0 + 1.5 * D.Streets;
		const double FromLayer = Clamp(0.6 * Params.MixedLayerMeters, 300.0, 3000.0);
		const double FromTiming = Clamp(Vp * Params.PuffIntervalSeconds / (1.3 * Elong), 300.0, 3000.0);
		D.PuffAcross = Clamp(std::sqrt(FromLayer * FromTiming), 300.0, 3000.0);
		D.PuffAlong = D.PuffAcross * Elong;
		D.SpacingAcross = 1.3 * D.PuffAcross * (1.0 + 0.4 * D.Streets);
		D.SpacingAlong = 1.3 * D.PuffAlong;
		D.Lifetime = Clamp(600.0 * std::sqrt(D.PuffAcross / 800.0), 300.0, 1200.0);

		// The puff field's mean and spread (Ra Rc pi / 3 and / 5 are the integrals of (1 - r^2)^2 and its square over a
		// puff; envelope moments numerically with a 30 s growth), so the gusts average to the mean wind.
		double E1 = 0.0, E2 = 0.0;
		for (int K = 0; K < 400; ++K)
		{
			const double Env = Envelope((K + 0.5) / 400.0 * D.Lifetime, 30.0, D.Lifetime);
			E1 += Env;
			E2 += Env * Env;
		}
		E1 /= 400.0;
		E2 /= 400.0;
		const double Area = kPi * 0.25 * D.PuffAcross * D.PuffAlong / (D.SpacingAcross * D.SpacingAlong);
		PuffMean = E1 * Area / 3.0;
		const double Var = std::max(E2 * (1.0 + 0.09 / 3.0) * Area / 5.0 - PuffMean * PuffMean, 1e-6);
		// The intensity splits between puffs and the fine turbulence: more puffs when the air is unstable. Or the weather
		// gives both (station calibration): the puffs then strengthen in unstable air and weaken in stable.
		const double GI = std::max(Params.GustIntensity, 0.0);
		double PuffTarget;
		if (Params.PuffIntensity >= 0.0)
		{
			// Stable air over the water damps them, unless the land around is convecting deep (a hot afternoon on a small
			// lake: the puffs come down from the mixed layer overhead whatever the water does).
			PuffTarget = Params.PuffIntensity / kPuffSlowRms * (1.0 + 0.4 * Unstable - 0.4 * Stable * (1.0 - SmoothStep(800.0, 2000.0, Params.MixedLayerMeters)));
			D.FineSigma = GI;
		}
		else
		{
			const double Share = Clamp(0.45 + 0.35 * Unstable - 0.35 * Stable - 0.3 * (1.0 - SmoothStep(300.0, 800.0, Params.MixedLayerMeters)), 0.1, 0.85);
			PuffTarget = GI * std::sqrt(Share);
		}
		D.PuffAmplitude = std::min(PuffTarget / std::sqrt(Var), 0.45);
		D.PuffSigma = D.PuffAmplitude * std::sqrt(Var);
		if (Params.PuffIntensity < 0.0) D.FineSigma = std::sqrt(std::max(GI * GI - D.PuffSigma * D.PuffSigma, 0.16 * GI * GI));
		D.bGusty = D.FineSigma > 0.0 || D.PuffAmplitude > 0.0;
	}

	double FWindField::Profile(double HeightMeters) const
	{
		const double Z = std::max(HeightMeters, 0.05);
		const double Log = std::log(Z / Params.RoughnessLength);
		return ObukhovL >= 1e8 ? Log : Log - PsiM(Z / ObukhovL);
	}

	double FWindField::MeanSpeedAtHeight(double HeightMeters) const
	{
		return MeanSpeed10 * Profile(HeightMeters) / ProfileNorm;
	}

	double FWindField::PuffField(double Along, double Across, double T, double& Fan) const
	{
		Fan = 0.0;
		if (D.PuffAmplitude <= 0.0) return 0.0;
		const double A = D.SpacingAlong, C = D.SpacingAcross;
		const double Ra = 0.5 * D.PuffAlong, Rc = 0.5 * D.PuffAcross;
		const int64_t I = int64_t(std::floor(Along / A)), J = int64_t(std::floor(Across / C));
		const double JitterAcross = 0.3 - 0.22 * D.Streets; // streets keep to their lanes
		double P = 0.0;
		for (int64_t DI = -1; DI <= 1; ++DI)
		{
			for (int64_t DJ = -1; DJ <= 1; ++DJ)
			{
				const int64_t CI = I + DI, CJ = J + DJ;
				// Each cell hosts a puff at a time, one generation after another, its own life and phase.
				const uint64_t Cell = CellHash(CI, CJ, -7, Params.Seed);
				const double Life = D.Lifetime * (0.8 + 0.4 * U01(Cell, 0));
				const double Cycle = T / Life + U01(Cell, 1);
				const double G = std::floor(Cycle);
				const double Age = (Cycle - G) * Life;
				const uint64_t H = CellHash(CI, CJ, int64_t(G), Params.Seed);
				const double Env = Envelope(Age, 20.0 + 20.0 * U01(H, 0), Life);
				if (Env <= 0.0) continue;
				const double CA = (CI + 0.5 + 0.6 * (U01(H, 1) - 0.5)) * A;
				const double CC = (CJ + 0.5 + 2.0 * JitterAcross * (U01(H, 2) - 0.5)) * C;
				const double Da = (Along - CA) / Ra, Dc = (Across - CC) / Rc;
				const double R2 = Da * Da + Dc * Dc;
				if (R2 >= 1.0) continue;
				const double W = (1.0 - R2) * (1.0 - R2);
				const double Strength = Env * (0.7 + 0.6 * U01(H, 3));
				P += Strength * W;
				// Fanning out: the side of the puff to the right of its track turns right, the left side left (peak 1).
				Fan += Strength * W * Dc * 3.5;
			}
		}
		return P;
	}

	void FWindField::Fine(double X, double Y, double T, double& DU, double& DV) const
	{
		double Along, Across;
		Air.Local(X, Y, T, Along, Across);
		if (const FTurbulenceTile* Tile = FTurbulenceTile::Shared())
		{
			// Read on a line slanted 1 in 7.3 across the periodic tile: a fixed point then never sees the tile's period come
			// round again (the eddies seem turned 8 degrees from the wind, well within what the wind's own shifts do).
			Tile->Sample(Along, Across + Along * (1.0 / 7.3), DU, DV);
			return;
		}
		// Stand-in without the tile (standalone tools that did not load it): a few incommensurate waves.
		const double* Ph = &Phases[8];
		DU = 0.6 * std::sin(Along / 41.0 + Ph[0]) * std::cos(Across / 57.0 + Ph[1]) + 0.5 * std::sin(Along / 13.3 + Across / 21.0 + Ph[2])
			+ 0.4 * std::sin(Along / 5.1 - Across / 7.7 + Ph[3]);
		DV = 0.55 * std::cos(Along / 37.0 + Ph[1]) * std::sin(Across / 49.0 + Ph[2]) + 0.35 * std::sin(Along / 11.1 - Across / 17.0 + Ph[0]);
	}

	double FWindField::Slow(double Along, double Across, double T) const
	{
		double Shift = 0.0;
		if (Params.ShiftDegrees > 0.0)
		{
			// Oscillating shifts: bands across the wind passing at the mean speed, a little ragged across it.
			const double Wavelength = std::max(MeanSpeed10, 0.5) * Params.ShiftPeriodSeconds;
			const double S = -Along / Wavelength * 2.0 * kPi + 0.5 * std::sin(Across / 2500.0 * 2.0 * kPi + Phases[4]);
			Shift += Params.ShiftDegrees * kDegToRad * 1.4
				* (0.55 * std::sin(S + Phases[0]) + 0.3 * std::sin(1.618 * S + Phases[1]) + 0.15 * std::sin(2.71 * S + Phases[2]));
		}
		if (Params.PersistentShiftDegrees != 0.0)
		{
			// A persistent swing: slow, the same everywhere on the water (the gradient wind turning, a sea breeze filling).
			Shift += Params.PersistentShiftDegrees * kDegToRad * (0.75 * std::sin(T / 3600.0 * 2.0 * kPi + Phases[5]) + 0.25 * std::sin(T / 1500.0 * 2.0 * kPi + Phases[6]));
		}
		return Shift;
	}

	void FWindField::PuffAt(double X, double Y, double T, double& OutFactor, double& OutShift) const
	{
		double Along, Across, Fan;
		Puffs.Local(X, Y, T, Along, Across);
		const double P = PuffField(Along, Across, T, Fan);
		OutFactor = 1.0 + D.PuffAmplitude * (P - PuffMean);
		// Veer and fan scale with how strong the puffs are (a whisper of a puff hardly turns the wind).
		const double Scale = std::min(1.0, D.PuffAmplitude / 0.2);
		OutShift = Scale * (Params.PuffVeerDegrees * (P - PuffMean) / std::max(1.0 - PuffMean, 0.3) + Params.PuffFanDegrees * Fan) * kDegToRad;
	}

	void FWindField::ReadableAt(double X, double Y, double T, double& OutFromRadians, double& OutFactor) const
	{
		double Along, Across;
		Air.Local(X, Y, T, Along, Across);
		double Shift = Slow(Along, Across, T), Factor = 1.0;
		if (D.bGusty)
		{
			double PuffShift;
			PuffAt(X, Y, T, Factor, PuffShift);
			Shift += PuffShift;
		}
		if (Shelter) Factor *= Shelter->FactorAt(X, Y);
		// Downwind direction turned by the shift; it comes from the opposite way.
		OutFromRadians = WrapAngle(std::atan2(DownwindDir.Y, DownwindDir.X) + Shift + kPi);
		OutFactor = Factor;
	}

	double FWindField::GustFactorAt(const Vec3& WorldPos, double TimeSeconds) const
	{
		if (!D.bGusty) return 1.0;
		double Factor, Shift, DU, DV;
		PuffAt(WorldPos.X, WorldPos.Y, TimeSeconds, Factor, Shift);
		Fine(WorldPos.X, WorldPos.Y, TimeSeconds, DU, DV);
		return std::max(0.2, Factor + D.FineSigma * DU);
	}

	double FWindField::ShiftAt(const Vec3& WorldPos, double TimeSeconds) const
	{
		double Along, Across;
		Air.Local(WorldPos.X, WorldPos.Y, TimeSeconds, Along, Across);
		double Shift = Slow(Along, Across, TimeSeconds);
		if (D.bGusty)
		{
			double Factor, PuffShift, DU, DV;
			PuffAt(WorldPos.X, WorldPos.Y, TimeSeconds, Factor, PuffShift);
			Fine(WorldPos.X, WorldPos.Y, TimeSeconds, DU, DV);
			const double G = std::max(0.2, Factor + D.FineSigma * DU);
			Shift += PuffShift + std::atan(D.FineSigma * DV / G);
		}
		return Shift;
	}

	Vec3 FWindField::VelocityAt(const Vec3& WorldPos, double TimeSeconds) const
	{
		double Along, Across;
		Air.Local(WorldPos.X, WorldPos.Y, TimeSeconds, Along, Across);
		double Shift = Slow(Along, Across, TimeSeconds);
		double Gust = 1.0, DU = 0.0, DV = 0.0;
		if (D.bGusty || Shelter)
		{
			Fine(WorldPos.X, WorldPos.Y, TimeSeconds, DU, DV);
		}
		if (D.bGusty)
		{
			double PuffShift;
			PuffAt(WorldPos.X, WorldPos.Y, TimeSeconds, Gust, PuffShift);
			Gust = std::max(0.2, Gust + D.FineSigma * DU);
			Shift += PuffShift + std::atan(D.FineSigma * DV / Gust);
		}
		const double Speed = MeanSpeedAtHeight(WorldPos.Z) * Gust;
		const double C = std::cos(Shift), S = std::sin(Shift);
		const Vec3 Dir(DownwindDir.X * C - DownwindDir.Y * S, DownwindDir.X * S + DownwindDir.Y * C, 0.0);
		Vec3 Wind = Dir * Speed;
		if (Shelter)
		{
			// In the lee of a point, a treeline or houses, and close downwind of any shore: less wind, and what is left is
			// gustier (the land's turbulence, the same eddies stretched).
			const double F = Shelter->FactorAt(WorldPos.X, WorldPos.Y);
			if (F < 0.999)
			{
				const double Turbulence = 1.0 + (1.0 - F) * 1.2 * DU * 0.5;
				Wind *= F * std::max(0.3, Turbulence);
			}
		}

		if (Front.bActive && TimeSeconds >= Front.StartTime)
		{
			const double Ahead = Front.DistanceAhead(WorldPos.X, WorldPos.Y, TimeSeconds);
			const double Blend = Front.Behind(WorldPos.X, WorldPos.Y, TimeSeconds);
			if (Blend > 0.0)
			{
				// Outflow: the cold pool spreading from the storm, strongest just behind its head, with its own fast,
				// violent gusts; and near the rain core the microburst's outflow on top.
				const double OutFrom = Front.OutflowFromDegrees * kDegToRad;
				const Vec3 OutDir(-std::cos(OutFrom), -std::sin(OutFrom), 0.0);
				const double Profile = std::log(std::max(WorldPos.Z, 0.05) / Params.RoughnessLength) / std::log(10.0 / Params.RoughnessLength);
				const double Behind = std::max(0.0, -Ahead);
				const double EdgeBoost = 1.0 + 0.15 * std::exp(-Behind / 400.0);
				const double S2 = (WorldPos.Dot(OutDir) - Front.OutflowKnots * kKnot * TimeSeconds) / 120.0 * 2.0 * kPi;
				const double* P = &Phases[4];
				const double Noise = 0.45 * std::sin(S2 + P[0]) + 0.30 * std::sin(S2 * 2.137 + P[1]) + 0.15 * std::sin(S2 * 3.613 + P[2]) + 0.10 * std::sin(S2 * 5.271 + P[3]);
				const double Gust2 = std::max(0.3, 1.0 + Front.OutflowGustIntensity * 1.6 * Noise);
				Vec3 Outflow = OutDir * (Front.OutflowKnots * kKnot * Profile * EdgeBoost);
				const Vec3 Burst = Front.BurstAt(WorldPos.X, WorldPos.Y, WorldPos.Z, TimeSeconds);
				Outflow += Vec3(Burst.X, Burst.Y, 0.0);
				Wind = Wind * (1.0 - Blend) + Outflow * (Gust2 * Blend);
			}
		}
		return Wind;
	}

	double FWindField::SurfaceRoughnessAt(double X, double Y, double TimeSeconds) const
	{
		return VelocityAt(Vec3(X, Y, 10.0), TimeSeconds).LengthXY() / 8.0;
	}

	double FWindField::MeanSurfaceRoughnessAt(double X, double Y, double TimeSeconds) const
	{
		double Speed = MeanSpeed10;
		if (const double W = Front.Behind(X, Y, TimeSeconds); W > 0.0)
		{
			const double From = Front.OutflowFromDegrees * kDegToRad;
			const Vec3 Burst = Front.BurstAt(X, Y, 10.0, TimeSeconds);
			const double Out = Vec3(-std::cos(From) * Front.OutflowKnots * kKnot + Burst.X, -std::sin(From) * Front.OutflowKnots * kKnot + Burst.Y, 0.0).LengthXY();
			Speed += (Out - Speed) * W;
		}
		return Speed / 8.0;
	}
}
