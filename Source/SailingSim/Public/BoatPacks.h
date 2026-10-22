#pragma once

#include "CoreMinimal.h"

// pc/boat-slots: the boat library's slots folded into packs, one material slot (a draw, a Nanite shading bin) each. A
// packed face keeps its library slot as an entry index in UV1.x; MI_Boat_<Pack> (make_materials.py, parent
// M_BoatPacked) holds entry k's values, its colour in P<k>C. Mirrors Tools/blender/boat_packs.json, held in step by
// SailingSim.Visual.BoatPacks: append entries, never reorder (imported meshes carry the indices).
namespace SailingBoatPacks
{
	/** The library slots a packed slot draws, in entry order; empty for a slot that isn't a pack. */
	inline TConstArrayView<const TCHAR*> Entries(FName Slot)
	{
		static const TCHAR* Canoe[] = { TEXT("Topsides"), TEXT("Bootstripe"), TEXT("CoveStripe"), TEXT("Antifouling") };
		static const TCHAR* Deck[] = { TEXT("Deck"), TEXT("NonSkid"), TEXT("Teak"), TEXT("Graphics"), TEXT("Keel"), TEXT("CabinWindow"), TEXT("Rubrail"), TEXT("Carbon") };
		static const TCHAR* Fit[] = { TEXT("Stainless"), TEXT("Aluminium"), TEXT("BlackPlastic"), TEXT("Wood"), TEXT("Rope"), TEXT("PaintedAluminium"), TEXT("Rubber"), TEXT("CarbonMatte") };
		static const TCHAR* Canvas[] = { TEXT("SailCover"), TEXT("SailCoverRed"), TEXT("SailCoverGreen"), TEXT("SailCoverTan"), TEXT("Tarp"), TEXT("Dacron"), TEXT("FenderBlue"), TEXT("CoolerLid") };
		if (Slot == TEXT("PackCanoe")) return Canoe;
		if (Slot == TEXT("PackDeck")) return Deck;
		if (Slot == TEXT("PackFit")) return Fit;
		if (Slot == TEXT("PackCanvas")) return Canvas;
		// The hero J/22's hardware pack (Inputs/j22-hero/J22H_packs.json; only the metal pack is read here, for the spars).
		static const TCHAR* HeroMetal[] = { TEXT("Stainless"), TEXT("Chrome"), TEXT("CastAlu"), TEXT("Aluminium"), TEXT("SheaveGrey"), TEXT("RigTape"), TEXT("TeakVarnish"), TEXT("Gelcoat") };
		if (Slot == TEXT("J22H_PackMetal")) return HeroMetal;
		return {};
	}

	inline const TCHAR* const PackNames[] = { TEXT("PackCanoe"), TEXT("PackDeck"), TEXT("PackFit"), TEXT("PackCanvas") };

	/** Entry K's colour parameter on a pack's material. */
	inline FName ColourParam(int32 K) { return FName(*FString::Printf(TEXT("P%dC"), K)); }

	/** Is this slot (a library slot, or a pack holding one) part of the canoe body (J22Mesh, FleetMesh)? */
	inline bool IsCanoeSlot(FName Slot)
	{
		return Slot == TEXT("PackCanoe") || Slot == TEXT("Topsides") || Slot == TEXT("Bootstripe") || Slot == TEXT("CoveStripe") || Slot == TEXT("Antifouling");
	}
}
