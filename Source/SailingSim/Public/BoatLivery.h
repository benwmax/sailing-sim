#pragma once

#include "CoreMinimal.h"

/**
 * Graphics G3: each boat's colours and wear, drawn from the boat catalogue (Inputs/g3/boat-catalogue.json, sourced per
 * class: builders' schemes weighted by how common they are, stripes, teak or stainless trim, wear zones with intensity
 * ranges per profile). Tools/fleet/make_liveries.py generates the table (BoatLiveryData.inl). A seed picks a scheme by
 * weight, a profile (club, race, charter) by weight, each wear channel uniformly in that profile's range, and a sail
 * number from the class's range. M_BoatSurface draws the wear (make_materials.py, BOAT_CODE).
 */
struct FLiveryScheme
{
	float Weight;
	FLinearColor Hull, Deck, NonSkid, Bottom;
	bool bBoot; FLinearColor Boot;
	bool bCove; FLinearColor Cove;
	bool bSheer; FLinearColor Sheer;
	bool bTeak; FLinearColor Teak;
};
struct FLiveryWear
{
	float Club, Race, Charter;          // profile weights
	float ClubRange[4][2], RaceRange[4][2], CharterRange[4][2]; // oxidation, waterline scum, scuffs, rust: [min, max]
	float FadeRange[3][2];              // the coloured sails' sun fade per profile (club, race, charter): [min, max]
};
struct FLiveryNumbers { bool bRequired; float Probability; int32 Lo, Hi; const TCHAR* Format; };
struct FLiveryClass { const FLiveryScheme* Schemes; int32 NumSchemes; const FLiveryWear* Wear; const FLiveryNumbers* Numbers; };

struct SAILINGSIM_API FBoatLivery
{
	FLinearColor Hull = FLinearColor(0.8f, 0.8f, 0.77f), Deck = FLinearColor(0.8f, 0.8f, 0.76f), NonSkid = FLinearColor(0.7f, 0.7f, 0.66f);
	FLinearColor Bottom = FLinearColor(0.015f, 0.022f, 0.05f), Boot = FLinearColor(0.01f, 0.018f, 0.08f), Cove = FLinearColor(0.01f, 0.018f, 0.08f);
	bool bBoot = true, bCove = true, bTeak = false;
	FLinearColor Teak = FLinearColor(0.25f, 0.23f, 0.2f);
	FVector4f Wear = FVector4f(0.f, 0.f, 0.f, 0.f);   // oxidation, waterline scum, scuffs, rust (0..1)
	float SailFade = 0.f;                             // the coloured sails' sun fade (0..1; M_SailCloth's Fade)
	int32 Scheme = 0, Profile = 0;                    // profile: 0 club, 1 race, 2 charter
	FString SailNumber;                               // empty: none
};

/** A boat's livery for a class (EBoatType as int) and seed. Seed 0 is the class's most common scheme as a club boat with
 *  middling wear (the player's boat). */
SAILINGSIM_API FBoatLivery SampleBoatLivery(int32 BoatType, uint32 Seed);
/** Number of colour schemes the catalogue lists for a class (tests). */
SAILINGSIM_API int32 NumLiverySchemes(int32 BoatType);
