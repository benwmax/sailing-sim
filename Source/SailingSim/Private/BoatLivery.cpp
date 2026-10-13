#include "BoatLivery.h"

namespace
{
#include "BoatLiveryData.inl"

	struct FRng
	{
		uint32 S;
		float Next() { S ^= S << 13; S ^= S >> 17; S ^= S << 5; return (S & 0xFFFFFF) / float(0x1000000); }
	};
}

int32 NumLiverySchemes(int32 BoatType)
{
	return BoatType >= 0 && BoatType < int32(UE_ARRAY_COUNT(LiveryClasses)) ? LiveryClasses[BoatType].NumSchemes : 0;
}

FBoatLivery SampleBoatLivery(int32 BoatType, uint32 Seed)
{
	FBoatLivery L;
	if (BoatType < 0 || BoatType >= int32(UE_ARRAY_COUNT(LiveryClasses))) return L;
	const FLiveryClass& C = LiveryClasses[BoatType];
	FRng R{ Seed * 2654435761u + 0x9e3779b9u + uint32(BoatType) * 97u };
	for (int32 K = 0; K < 4; ++K) R.Next();
	// The scheme, by weight (seed 0: the most common).
	int32 Pick = 0;
	if (Seed != 0)
	{
		float Total = 0.f;
		for (int32 I = 0; I < C.NumSchemes; ++I) Total += C.Schemes[I].Weight;
		float X = R.Next() * Total;
		for (Pick = 0; Pick < C.NumSchemes - 1; ++Pick)
		{
			X -= C.Schemes[Pick].Weight;
			if (X < 0.f) break;
		}
	}
	const FLiveryScheme& S = C.Schemes[Pick];
	L.Scheme = Pick;
	L.Hull = S.Hull; L.Deck = S.Deck; L.NonSkid = S.NonSkid; L.Bottom = S.Bottom;
	L.bBoot = S.bBoot; L.Boot = S.bBoot ? S.Boot : S.Hull;
	L.bCove = S.bCove; L.Cove = S.bCove ? S.Cove : S.Hull;
	L.bTeak = S.bTeak; L.Teak = S.Teak;
	// The wear profile, by weight; seed 0: a club boat at the middle of its ranges.
	const FLiveryWear& W = *C.Wear;
	if (Seed != 0)
	{
		const float X = R.Next() * (W.Club + W.Race + W.Charter);
		L.Profile = X < W.Club ? 0 : (X < W.Club + W.Race ? 1 : 2);
	}
	else
	{
		L.Profile = W.Club > 0.f ? 0 : 2;
	}
	const float (*Range)[2] = L.Profile == 0 ? W.ClubRange : (L.Profile == 1 ? W.RaceRange : W.CharterRange);
	for (int32 K = 0; K < 4; ++K)
	{
		const float T = Seed == 0 ? 0.5f : R.Next();
		L.Wear[K] = FMath::Lerp(Range[K][0], Range[K][1], T);
	}
	// The sail number, from the class's range and format ("USA {n}", "{n}", "{n6}": six digits).
	const FLiveryNumbers& N = *C.Numbers;
	if (N.bRequired || R.Next() < N.Probability)
	{
		const int32 Num = Seed == 0 ? FMath::Clamp(1288, N.Lo, N.Hi) : N.Lo + int32(R.Next() * float(N.Hi - N.Lo));
		FString Fmt(N.Format);
		const FString Digits = Fmt.Contains(TEXT("{n6}")) ? FString::Printf(TEXT("%06d"), Num) : FString::FromInt(Num);
		L.SailNumber = Fmt.Replace(TEXT("{n6}"), *Digits).Replace(TEXT("{n}"), *Digits);
	}
	return L;
}
