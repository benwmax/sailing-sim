#pragma once

#include "CoreMinimal.h"

class UTextureRenderTarget2D;

/**
 * The boat's name on her hull (docs/skins/README.md, "Name on the hull"): a skin's lettering (FBoatSkin::FLettering) as
 * vinyl letters on both quarters. The name is drawn once into a small texture with the menus' title face (Draw), and the
 * hull's material lays it on the topsides by a side-on projection in the hull's own frame (M_J22HeroSurface's NameTex,
 * NameRect and NameColour: scripts/import_j22_hero.py), so it follows the hull's curve as cut vinyl does and takes the
 * boat's wear. Each side reads from her bow end to her stern end as you stand beside her.
 *
 * Only the hero J/22 has the material for it so far: her transom carries the rudder and the outboard bracket, so the name
 * goes on the quarters, as most J/22s wear it.
 */
struct FHullNamePlace
{
	float XAftCm = 0.f;     // the lettering's aft edge, in the hull's frame (X forward, origin on the design waterline)
	float ZLowCm = 0.f;     // its lower edge above the waterline
	float LengthCm = 1.f;   // along the hull
	float HeightCm = 1.f;   // the texture's height: the capitals are about half of it
	/** M_J22HeroSurface's NameRect. */
	FLinearColor AsParam() const { return FLinearColor(XAftCm, ZLowCm, LengthCm, HeightCm); }
};

namespace SailingHullName
{
	/** Where a class wears her name, for a texture Aspect (width over height) wide. False: this class has no place for
	 *  one yet. A long name is made smaller to fit the place's length, about its middle height. */
	SAILINGSIM_API bool Place(int32 BoatType, float Aspect, FHullNamePlace& Out);
	/** The name in white on black, as a texture (its red channel is the letters' cover). Null without a renderer (tests,
	 *  -nullrhi) or a name. OutSizePx is the texture's size. Outer keeps it alive only if it holds the pointer. */
	SAILINGSIM_API UTextureRenderTarget2D* Draw(UObject* Outer, const FString& Name, FVector2D& OutSizePx);
}
