#include "Marina.h"
#include "BoatModel.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	TArray<FVector2D> ReadPoints(const TSharedPtr<FJsonObject>& O)
	{
		TArray<FVector2D> P;
		for (const TSharedPtr<FJsonValue>& V : O->GetArrayField(TEXT("points")))
		{
			const TArray<TSharedPtr<FJsonValue>>& XY = V->AsArray();
			P.Add(FVector2D(XY[0]->AsNumber(), XY[1]->AsNumber()));
		}
		return P;
	}

	void ReadLines(const TSharedPtr<FJsonObject>& Root, const TCHAR* Field, TArray<FMarinaLine>& Out, float DefaultHeight)
	{
		const TArray<TSharedPtr<FJsonValue>>* Arr;
		if (!Root->TryGetArrayField(Field, Arr)) return;
		for (const TSharedPtr<FJsonValue>& V : *Arr)
		{
			const TSharedPtr<FJsonObject> O = V->AsObject();
			FMarinaLine L;
			L.Id = O->GetStringField(TEXT("id"));
			L.Points = ReadPoints(O);
			O->TryGetNumberField(TEXT("width"), L.Width);
			L.Height = DefaultHeight;
			O->TryGetNumberField(TEXT("height"), L.Height);
			Out.Add(L);
		}
	}

	uint32 SlipHash(uint32 X)
	{
		X ^= X >> 16; X *= 0x7feb352dU; X ^= X >> 15; X *= 0x846ca68bU; X ^= X >> 16;
		return X;
	}
}

bool FMarina::Load(const FString& Path)
{
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *Path)) return false;
	TSharedPtr<FJsonObject> Root;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root) return false;
	Name = Root->GetStringField(TEXT("name"));
	ReadLines(Root, TEXT("walkways"), Walkways, 0.6f);
	ReadLines(Root, TEXT("piers"), Piers, 0.9f);
	ReadLines(Root, TEXT("breakwaters"), Breakwaters, 1.5f);
	for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("rows")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		FMarinaRow R;
		R.Id = O->GetStringField(TEXT("id"));
		R.Points = ReadPoints(O);
		O->TryGetNumberField(TEXT("width"), R.Width);
		O->TryGetNumberField(TEXT("slip_width"), R.SlipWidth);
		O->TryGetNumberField(TEXT("finger_length"), R.FingerLength);
		O->TryGetNumberField(TEXT("start_offset"), R.StartOffset);
		R.Height = 0.45f; // floating docks
		Rows.Add(R);
	}
	for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("buildings")))
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		FMarinaBuilding B;
		B.Id = O->GetStringField(TEXT("id"));
		B.Kind = O->GetStringField(TEXT("kind"));
		const TArray<TSharedPtr<FJsonValue>>& C = O->GetArrayField(TEXT("center"));
		const TArray<TSharedPtr<FJsonValue>>& S = O->GetArrayField(TEXT("size"));
		B.Center = FVector2D(C[0]->AsNumber(), C[1]->AsNumber());
		B.Size = FVector2D(S[0]->AsNumber(), S[1]->AsNumber());
		O->TryGetNumberField(TEXT("heading"), B.HeadingDeg);
		O->TryGetNumberField(TEXT("height"), B.Height);
		O->TryGetNumberField(TEXT("roof"), B.Roof);
		Buildings.Add(B);
	}
	double Occupancy = 0.65;
	Root->TryGetNumberField(TEXT("occupancy"), Occupancy);
	FString HomeRow;
	int32 HomeSide = 1, HomeIndex = 0;
	const TSharedPtr<FJsonObject>* Home;
	if (Root->TryGetObjectField(TEXT("home_slip"), Home))
	{
		HomeRow = (*Home)->GetStringField(TEXT("row"));
		(*Home)->TryGetNumberField(TEXT("side"), HomeSide);
		(*Home)->TryGetNumberField(TEXT("index"), HomeIndex);
	}

	// Slips along each row, both sides: a finger pier between each pair of berths, out at right angles.
	for (int32 RI = 0; RI < Rows.Num(); ++RI)
	{
		const FMarinaRow& R = Rows[RI];
		const FVector2D A = R.Points[0], B = R.Points.Last();
		const FVector2D Dir = (B - A).GetSafeNormal(), Left(-Dir.Y, Dir.X);
		const float Length = float(FVector2D::Distance(A, B));
		const int32 Count = FMath::Max(0, int32((Length - R.StartOffset - 2.f) / R.SlipWidth));
		for (int32 Side : { 1, -1 })
		{
			const FVector2D Out = Left * double(Side);
			for (int32 I = 0; I < Count; ++I)
			{
				const double Along = R.StartOffset + (I + 0.5) * R.SlipWidth;
				FMarinaSlip S;
				S.Row = RI;
				S.Side = Side;
				S.Index = I;
				S.Id = FString::Printf(TEXT("%s.%s%02d"), *R.Id, Side > 0 ? TEXT("n") : TEXT("s"), I + 1);
				const double Off = 0.5 * R.Width + 0.5 * R.FingerLength + 0.4; // bow 0.6 m off the dock, stern a little past the finger
				S.Center = A + Dir * Along + Out * Off;
				// Bow in: the boat points at the row.
				const FVector2D In = -Out;
				S.HeadingDeg = float(FMath::RadiansToDegrees(FMath::Atan2(In.Y, In.X)));
				const FVector2D FingerRoot = A + Dir * (R.StartOffset + (I + 1) * R.SlipWidth) + Out * (0.5 * R.Width);
				S.FingerA = FingerRoot;
				S.FingerB = FingerRoot + Out * R.FingerLength;
				S.bHome = R.Id == HomeRow && Side == HomeSide && I == HomeIndex;
				S.bOccupied = !S.bHome && (SlipHash(uint32(RI * 1000 + (Side > 0 ? 0 : 500) + I) + 17u) & 0xFFFF) / 65535.0 < Occupancy;
				if (S.bHome) HomeSlip = Slips.Num();
				Slips.Add(S);
			}
		}
	}
	return true;
}

void FMarina::PlaceAlongside(TFunctionRef<double(double, double)> DepthAt)
{
	Alongside.Reset();
	const Sailing::FBoatConfig C30 = Sailing::FBoatConfig::Make(Sailing::EBoatType::Catalina30);
	// Not lying over a launch ramp (PlaceRamps first): the slab runs out under the water beside its pier.
	auto OverRamp = [&](const FVector2D& P)
	{
		for (const FMarinaRamp& R : Ramps)
		{
			const FVector2D A = 0.5 * (R.In + R.Out), AB = R.Dir * R.Length;
			const double T = FMath::Clamp(FVector2D::DotProduct(P - A, AB) / AB.SizeSquared(), 0.0, 1.0);
			if (FVector2D::Distance(P, A + AB * T) < 0.5 * FMarinaRamp::Width + 0.5 * C30.Beam + 0.5) return true;
		}
		return false;
	};
	for (const FMarinaLine& L : Piers)
	{
		for (int32 I = 1; I < L.Points.Num(); ++I)
		{
			const FVector2D A = L.Points[I - 1], B = L.Points[I];
			const double Len = FVector2D::Distance(A, B);
			const FVector2D Dir = (B - A) / FMath::Max(Len, 1e-3), Left(-Dir.Y, Dir.X);
			for (double At = 0.5 * C30.LengthOverall + 1.5; At + 0.5 * C30.LengthOverall < Len; At += C30.LengthOverall + 2.0)
			{
				for (const double Side : { 1.0, -1.0 })
				{
					const FVector2D Center = A + Dir * At + Left * (Side * (0.5 * L.Width + 0.5 * C30.Beam + 0.35));
					if (DepthAt(Center.X, Center.Y) < C30.Draft + 0.3 || OverRamp(Center)) continue;
					FMarinaAlongside B30;
					B30.Center = Center;
					B30.HeadingDeg = float(FMath::RadiansToDegrees(FMath::Atan2(Dir.Y, Dir.X)));
					B30.BoatType = uint8(Sailing::EBoatType::Catalina30);
					Alongside.Add(B30);
					break;
				}
			}
		}
	}
}

void FMarina::PlaceRamps(TFunctionRef<double(double, double)> HeightAt)
{
	// A ramp starts on ground at least this high above the water: a pier's shore end can stand in the shallows (Rush
	// Creek's does, about 15 m off the beach), and a slab begun there would float off the end of the pier.
	constexpr double DryGround = 0.4;
	Ramps.Reset();
	for (const FMarinaLine& L : Piers)
	{
		if (!L.Id.EndsWith(TEXT(".ramp")) || L.Points.Num() < 2) continue;
		FVector2D Shore = L.Points[0], Sea = L.Points[1];
		if (HeightAt(Sea.X, Sea.Y) > HeightAt(Shore.X, Shore.Y)) Swap(Shore, Sea);
		FMarinaRamp R;
		R.PierId = L.Id;
		R.Dir = (Sea - Shore).GetSafeNormal();
		const FVector2D Side(-R.Dir.Y, R.Dir.X);
		// Beside the pier (a metre clear of its edge), the head walked back up the beach a metre at a time, then a metre more.
		FVector2D Head = Shore + Side * (0.5 * L.Width + 1.0 + 0.5 * FMarinaRamp::Width);
		for (int32 Step = 0; Step < 40 && HeightAt(Head.X, Head.Y) < DryGround; ++Step) Head -= R.Dir;
		Head -= R.Dir;
		R.In = Head - Side * (0.5 * FMarinaRamp::Width);
		R.Out = Head + Side * (0.5 * FMarinaRamp::Width);
		R.Top = float(FMath::Max3(HeightAt(R.In.X, R.In.Y), HeightAt(R.Out.X, R.Out.Y), 0.3)) + 0.05f;
		// The foot where the ground on the slab's centre line first reaches Foot: a straight slab from the head to there
		// follows the bank down into the water, cut in level across it (the 1 m club shore drops 2 m in 7 m, where an 18 m
		// slab stood up to 0.6 m out of the water for 5 m past the shore; it also falls about 0.8 m across the slab's 5 m,
		// from the pier side, so the bank covers that edge a little and the far kerb stands out of it).
		R.Length = FMarinaRamp::MaxLength;
		for (double Along = FMarinaRamp::MinLength; Along <= FMarinaRamp::MaxLength; Along += 0.25)
		{
			const FVector2D Mid = 0.5 * (R.In + R.Out) + R.Dir * Along;
			if (HeightAt(Mid.X, Mid.Y) <= FMarinaRamp::Foot)
			{
				R.Length = float(Along);
				break;
			}
		}
		Ramps.Add(R);
	}
}

void FMarina::ForEachObstacleLine(TFunctionRef<void(const TArray<FVector2D>&, const FString&, float)> Visit) const
{
	for (const FMarinaLine& L : Walkways) Visit(L.Points, TEXT("marina"), 0.5f * L.Width);
	for (const FMarinaLine& L : Piers) Visit(L.Points, TEXT("marina"), 0.5f * L.Width);
	for (const FMarinaLine& L : Breakwaters) Visit(L.Points, TEXT("breakwater"), 0.5f * L.Width);
	for (const FMarinaRow& R : Rows) Visit(R.Points, TEXT("marina"), 0.5f * R.Width);
	for (const FMarinaSlip& S : Slips)
	{
		// One finger per slip pair is enough: each slip's own finger (the last slip's other side is open water).
		Visit({ S.FingerA, S.FingerB }, TEXT("finger"), 0.3f);
	}
	// The berthed boats are in the way too (Visual V7): a capsule along each hull.
	auto Boat = [&](const FVector2D& Center, float HeadingDeg, uint8 Type)
	{
		const Sailing::FBoatConfig C = Sailing::FBoatConfig::Make(Sailing::EBoatType(Type));
		const FVector2D Fwd(FMath::Cos(FMath::DegreesToRadians(HeadingDeg)), FMath::Sin(FMath::DegreesToRadians(HeadingDeg)));
		const double Half = 0.5 * C.LengthOverall - 0.45 * C.Beam;
		Visit({ Center - Fwd * Half, Center + Fwd * Half }, TEXT("boat"), float(0.45 * C.Beam));
	};
	for (const FMarinaSlip& S : Slips) if (S.bOccupied) Boat(S.Center, S.HeadingDeg, S.BoatType);
	for (const FMarinaAlongside& A : Alongside) Boat(A.Center, A.HeadingDeg, A.BoatType);
	// A ramp only where it stands above the water: under it the slab is no higher than the bottom a boat grounds on.
	for (const FMarinaRamp& R : Ramps)
	{
		const FVector2D Head = 0.5 * (R.In + R.Out);
		Visit({ Head, Head + R.Dir * R.DryLength() }, TEXT("ramp"), 0.5f * FMarinaRamp::Width + 0.15f);
	}
}

FBox2D FMarina::Bounds(double Margin) const
{
	FBox2D Box(ForceInit);
	ForEachObstacleLine([&](const TArray<FVector2D>& Pts, const FString&, float) { for (const FVector2D& P : Pts) Box += P; });
	return Box.bIsValid ? Box.ExpandBy(Margin) : Box;
}
