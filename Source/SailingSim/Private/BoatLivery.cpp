#include "BoatLivery.h"
#include "BoatPacks.h"
#include "Components/MeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"

namespace
{
#include "BoatLiveryData.inl"

	struct FRng
	{
		uint32 S;
		float Next() { S ^= S << 13; S ^= S >> 17; S ^= S << 5; return (S & 0xFFFFFF) / float(0x1000000); }
	};
}

void PaintSpars(UMeshComponent* Part, const FBoatLivery& L)
{
	if (!Part || !L.bSparPainted) return;
	// make_materials.py BOAT_LIBRARY "PaintedAluminium": roughness 0.35, not metallic, clear coat 0.6, porosity 0.05; surface 5.
	const float Rough = 0.35f, Coat = 0.6f, Porosity = 0.05f, Surface = 5.f;
	const TArray<FName> Slots = Part->GetMaterialSlotNames();
	for (int32 I = 0; I < Slots.Num(); ++I)
	{
		const TConstArrayView<const TCHAR*> Packed = SailingBoatPacks::Entries(Slots[I]);
		const int32 Entry = Packed.IndexOfByPredicate([](const TCHAR* E) { return FCString::Strcmp(E, TEXT("Aluminium")) == 0; });
		const bool bOwn = Slots[I] == TEXT("Aluminium") || Slots[I] == TEXT("MastAluminium");
		if (!bOwn && Entry == INDEX_NONE) continue;
		UMaterialInstanceDynamic* Mid = Part->CreateDynamicMaterialInstance(I);
		if (!Mid) continue;
		if (bOwn)
		{
			Mid->SetVectorParameterValue(TEXT("Color"), L.Spar);
			Mid->SetScalarParameterValue(TEXT("Roughness"), Rough);
			Mid->SetScalarParameterValue(TEXT("Metallic"), 0.f);
			Mid->SetScalarParameterValue(TEXT("ClearCoat"), Coat);
			Mid->SetScalarParameterValue(TEXT("Porosity"), Porosity);
			Mid->SetScalarParameterValue(TEXT("Surface"), Surface);
			continue;
		}
		// A pack's entry: P<k>C colour, P<k>A (roughness, metallic, clear coat, non-skid), P<k>B (porosity, surface, hull, grain).
		Mid->SetVectorParameterValue(SailingBoatPacks::ColourParam(Entry), L.Spar);
		Mid->SetVectorParameterValue(FName(*FString::Printf(TEXT("P%dA"), Entry)), FLinearColor(Rough, 0.f, Coat, 0.f));
		Mid->SetVectorParameterValue(FName(*FString::Printf(TEXT("P%dB"), Entry)), FLinearColor(Porosity, Surface, 0.f, 0.f));
	}
}

int32 NumLiverySchemes(int32 BoatType)
{
	return BoatType >= 0 && BoatType < int32(UE_ARRAY_COUNT(LiveryClasses)) ? LiveryClasses[BoatType].NumSchemes : 0;
}

/**
 * The player's boat is 1288 where the class's numbers reach it; elsewhere the number in range nearest the middle that
 * keeps the most of its last digits (ILCA 161288, Corsair 188, Lagoon 288). Clamping read "100000" on the ILCA.
 */
static int32 PlayerSailNumber(int32 Lo, int32 Hi)
{
	if (1288 >= Lo && 1288 <= Hi) return 1288;
	const int32 Mid = Lo + (Hi - Lo) / 2;
	for (int32 M = 10000; M >= 10; M /= 10)
	{
		const int32 Num = Mid / M * M + 1288 % M;
		if (Num >= Lo && Num <= Hi) return Num;
	}
	return Mid;
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
	// Fleet hero (the Sunfish's dinghy park): the coloured sails' sun fade, from its own stream so the draws after it (the
	// sail number) are what they were.
	{
		FRng F{ Seed * 40503u + 0x51ed27u + uint32(BoatType) * 31u };
		for (int32 K = 0; K < 3; ++K) F.Next();
		const float* Fade = W.FadeRange[FMath::Clamp(L.Profile, 0, 2)];
		L.SailFade = FMath::Lerp(Fade[0], Fade[1], Seed == 0 ? 0.5f : F.Next());
	}
	// pc/j22-detail: the spars' finish, by weight from its own stream (seed 0: the first, the player's painted spars).
	if (C.NumSpars > 0)
	{
		int32 Spar = 0;
		if (Seed != 0)
		{
			FRng F{ Seed * 69069u + 0x2545f491u + uint32(BoatType) * 13u };
			for (int32 K = 0; K < 3; ++K) F.Next();
			float Total = 0.f;
			for (int32 I = 0; I < C.NumSpars; ++I) Total += C.Spars[I].Weight;
			float X = F.Next() * Total;
			for (Spar = 0; Spar < C.NumSpars - 1; ++Spar)
			{
				X -= C.Spars[Spar].Weight;
				if (X < 0.f) break;
			}
		}
		L.bSparPainted = C.Spars[Spar].bPainted;
		L.Spar = C.Spars[Spar].Colour;
	}
	// The sail number, from the class's range and format ("USA {n}", "{n}", "{n6}": six digits).
	const FLiveryNumbers& N = *C.Numbers;
	if (N.bRequired || R.Next() < N.Probability)
	{
		const int32 Num = Seed == 0 ? PlayerSailNumber(N.Lo, N.Hi) : N.Lo + int32(R.Next() * float(N.Hi - N.Lo));
		FString Fmt(N.Format);
		const FString Digits = Fmt.Contains(TEXT("{n6}")) ? FString::Printf(TEXT("%06d"), Num) : FString::FromInt(Num);
		L.SailNumber = Fmt.Replace(TEXT("{n6}"), *Digits).Replace(TEXT("{n}"), *Digits);
	}
	return L;
}
