#pragma once

#include "CoreMinimal.h"

/**
 * pc/crew-colours (docs/crew-colours): what a boat's crew wear, Bean's "lighter mix". Each sailor a light polo and a bright
 * life jacket (yellow, red or light blue), the palettes drawn from class-boat crews at regattas and sailing schools. Seeded
 * per boat like the livery (BoatLivery.h): seed 0 is the player's boat, a fixed set; AI boats seed from their unique id;
 * -SailingLiverySeed=<n> picks one for stills. Linear albedo, as M_CrewFabric's and the outfit materials' Color takes it.
 */
struct SAILINGSIM_API FCrewOutfit
{
	FLinearColor Polo = FLinearColor(0.80f, 0.80f, 0.78f);
	FLinearColor Vest = FLinearColor(0.70f, 0.02f, 0.02f);
};

/** One sailor's outfit: the boat's seed and the sailor's place in the crew (0 = the first figure). Seed 0 is the player's
 *  fixed set; any other seed draws from the palettes: a different polo for each of up to nine sailors, and the jackets'
 *  three colours in turn. */
SAILINGSIM_API FCrewOutfit SampleCrewOutfit(uint32 Seed, int32 Sailor);
/** The palettes' sizes (tests). */
SAILINGSIM_API int32 NumCrewPolos();
SAILINGSIM_API int32 NumCrewVests();
SAILINGSIM_API FLinearColor CrewPolo(int32 Index);
SAILINGSIM_API FLinearColor CrewVest(int32 Index);
