#pragma once

#include "CoreMinimal.h"

class UTexture2D;

/**
 * The boat's name on her hull (docs/skins/README.md, "Name on the hull"): a skin's lettering (FBoatSkin::FLettering) as
 * vinyl letters on both quarters. The name is drawn once per name into a small texture with the menus' title face (Draw), and the
 * hull's material lays it on the topsides by a side-on projection in the hull's own frame (M_J22HeroSurface's NameTex,
 * NameRect and NameColour: scripts/import_j22_hero.py), so it follows the hull's curve as cut vinyl does and takes the
 * boat's wear. Each side reads from her bow end to her stern end as you stand beside her.
 *
 * Every class wears it on her quarters (most transoms carry a rudder, a bracket or a ladder): the hero J/22 through
 * M_J22HeroSurface, the rest through M_BoatSurface's topsides (scripts/make_materials.py, BOAT_CODE), each lettered side
 * facing outboard, so a catamaran wears it on both hulls' outer sides. The frigate's name is carved on her stern.
 */
struct FHullNamePlace
{
	float XAftCm = 0.f;     // the lettering's aft edge, in the hull's frame (X forward, origin on the design waterline)
	float ZLowCm = 0.f;     // its lower edge above the waterline
	float LengthCm = 1.f;   // along the hull
	float HeightCm = 1.f;   // the texture's height: the capitals are about half of it
	float MaxSideCm = 1.0e6f; // how far out from her centreline (|Y|) a lettered side may be: a trimaran's main hull only
	/** The hull materials' NameRect. */
	FLinearColor AsParam() const { return FLinearColor(XAftCm, ZLowCm, LengthCm, HeightCm); }
	/** M_BoatSurface's NameSpan: the lettered sides' reach from the centreline. */
	FLinearColor AsSpan() const { return FLinearColor(0.f, MaxSideCm, 0.f, 0.f); }
};

namespace SailingHullName
{
	/** Where a class wears her name, for a texture Aspect (width over height) wide. False: this class has no place for
	 *  one yet. A long name is made smaller to fit the place's length, about its middle height. */
	SAILINGSIM_API bool Place(int32 BoatType, float Aspect, FHullNamePlace& Out);
	/** The name in white on black, as a texture (its red channel is the letters' cover). Null without a renderer (tests,
	 *  -nullrhi) or a name. OutSizePx is the texture's size. Outer keeps it alive only if it holds the pointer. It stalls
	 *  for a read-back, so keep the texture while the name is the same. */
	SAILINGSIM_API UTexture2D* Draw(UObject* Outer, const FString& Name, FVector2D& OutSizePx);
}
