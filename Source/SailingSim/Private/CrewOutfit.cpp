#include "CrewOutfit.h"

namespace
{
	// Light polos (sRGB as they'd be named, converted to linear albedo): white, ice grey, stone, pale blue, sky, aqua, soft
	// yellow, pale pink, sage. Club and school crews wear light tops in the Texas sun; none darker than stone (albedo ~0.4).
	const FLinearColor kPolos[] = {
		FLinearColor(0.80f, 0.80f, 0.78f),   // white (worn, not paper white)
		FLinearColor(0.58f, 0.60f, 0.61f),   // ice grey
		FLinearColor(0.52f, 0.47f, 0.37f),   // stone
		FLinearColor(0.40f, 0.53f, 0.72f),   // pale blue
		FLinearColor(0.30f, 0.52f, 0.76f),   // sky
		FLinearColor(0.33f, 0.62f, 0.60f),   // aqua
		FLinearColor(0.78f, 0.70f, 0.36f),   // soft yellow
		FLinearColor(0.76f, 0.47f, 0.47f),   // pale pink
		FLinearColor(0.43f, 0.55f, 0.40f),   // sage
	};
	// Life jackets: the bright nylon shells class-boat crews wear (yellow, red, light blue), two shades each (new, sun-faded).
	const FLinearColor kVests[] = {
		FLinearColor(0.85f, 0.56f, 0.01f),   // yellow
		FLinearColor(0.80f, 0.62f, 0.10f),   // yellow, faded
		FLinearColor(0.66f, 0.02f, 0.02f),   // red
		FLinearColor(0.58f, 0.07f, 0.06f),   // red, faded
		FLinearColor(0.07f, 0.38f, 0.78f),   // light blue
		FLinearColor(0.12f, 0.42f, 0.70f),   // light blue, faded
	};
	// The player's boat: white, pale blue and stone polos; red, yellow and light blue jackets.
	const int32 kPlayerPolos[] = { 0, 3, 2 };
	const int32 kPlayerVests[] = { 2, 0, 4 };

	uint32 Hash(uint32 X)
	{
		X ^= X >> 16; X *= 0x7feb352du; X ^= X >> 15; X *= 0x846ca68bu; X ^= X >> 16;
		return X;
	}
}

FCrewOutfit SampleCrewOutfit(uint32 Seed, int32 Sailor)
{
	FCrewOutfit O;
	const int32 S = FMath::Max(Sailor, 0);
	if (Seed == 0)
	{
		O.Polo = kPolos[kPlayerPolos[S % UE_ARRAY_COUNT(kPlayerPolos)]];
		O.Vest = kVests[kPlayerVests[S % UE_ARRAY_COUNT(kPlayerVests)]];
		return O;
	}
	// A boat's start in each palette, then a step per sailor coprime to its size, so a crew of up to its size never repeats.
	const uint32 H = Hash(Seed * 2654435761u + 0x9e3779b9u);
	const int32 NP = UE_ARRAY_COUNT(kPolos), NV = UE_ARRAY_COUNT(kVests);
	O.Polo = kPolos[(int32(H % uint32(NP)) + 2 * S) % NP];          // step 2 (9 polos)
	// Jackets by colour (yellow, red, light blue: three sailors three colours) and, separately, new or faded.
	const int32 Colour = (int32((H >> 8) % 3u) + S) % 3, Shade = int32((H >> 16) + uint32(S)) & 1;
	O.Vest = kVests[(2 * Colour + Shade) % NV];
	return O;
}

int32 NumCrewPolos() { return UE_ARRAY_COUNT(kPolos); }
int32 NumCrewVests() { return UE_ARRAY_COUNT(kVests); }
FLinearColor CrewPolo(int32 Index) { return kPolos[FMath::Clamp(Index, 0, NumCrewPolos() - 1)]; }
FLinearColor CrewVest(int32 Index) { return kVests[FMath::Clamp(Index, 0, NumCrewVests() - 1)]; }
