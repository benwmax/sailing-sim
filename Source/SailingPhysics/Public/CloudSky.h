#pragma once

#include "SailingPhysicsApi.h"
#include "Wind.h"
#include <functional>
#include <vector>

namespace Sailing
{
	/**
	 * Visual V5: the sky's clouds as layers, from the weather. Each layer has a coverage (the share of the sky it covers
	 * seen from below), a base and top (km above the water) and a density scale:
	 *  - fair-weather cumulus that builds after noon over the land (the Texas summer boundary layer: bases near 1.2 to
	 *    1.5 km, rising through the afternoon);
	 *  - a flat stratus or nimbostratus deck (overcast, rain);
	 *  - high cirrus (ahead of a front, a storm's anvil blow-off);
	 *  - the storm itself, whose shape is FStormShape (shelf cloud on the gust front, rain core, anvil).
	 */
	enum class ECloudLayer : uint8_t { Cumulus, Stratus, Cirrus, Storm, Count };
	SAILINGPHYSICS_API const char* CloudLayerName(ECloudLayer Layer);

	struct FCloudLayer
	{
		double Coverage = 0.0;
		double BaseKm = 1.4, TopKm = 2.6;
		double Density = 1.0;
	};

	struct SAILINGPHYSICS_API FCloudSky
	{
		FCloudLayer Layers[int(ECloudLayer::Count)];
		/** Humidity haze, 0 dry and crisp (a norther) .. 1 milky (a humid Texas summer morning). */
		double Haze = 0.3;
		/** Wind aloft (m/s, toward +X north / +Y east): the clouds drift with it. */
		double DriftX = 0.0, DriftY = 0.0;

		const FCloudLayer& operator[](ECloudLayer L) const { return Layers[int(L)]; }
		FCloudLayer& operator[](ECloudLayer L) { return Layers[int(L)]; }
		/** Lowest base and highest top of the volumetric layers present (what the renderer's cloud layer must span; cirrus
		 *  is drawn on the sky dome). */
		void Span(double& OutBaseKm, double& OutTopKm) const;
	};

	/**
	 * The thunderstorm's built structure, tied to the physics gust front (FGustFront). Distances are along the front's
	 * direction of travel: D = FGustFront::DistanceAhead (m, positive = ahead of the outflow). The material
	 * (make_materials.py, CLOUD_CODE) uses the same constants; SailingSim.Visual.ShelfCloud holds them to the front.
	 *  - Shelf cloud: a low wedge over the outflow's leading edge, ShelfLeadM ahead of the front at its lip, base about
	 *    ShelfBaseM, its smooth face sloping up and back into the storm.
	 *  - Rain core: from CoreBehindM behind the front, base CoreBaseM, towering to CoreTopM.
	 *  - Anvil: spreads ahead at AnvilBaseM to the top, thinning with distance ahead.
	 */
	struct SAILINGPHYSICS_API FStormShape
	{
		static constexpr double ShelfLeadM = 250.0;
		static constexpr double ShelfBaseM = 520.0;
		static constexpr double ShelfLipM = 180.0;    // thickness at the lip
		static constexpr double ShelfSlope = 0.85;    // face rise per metre back
		static constexpr double ShelfDepthM = 3500.0; // shelf to the core
		static constexpr double ShelfTierM = 700.0;   // W5a: the face climbs in broad tiers this far apart (three, then evenly)
		static constexpr double CoreBehindM = 700.0;   // the rain starts about a minute after the front (FWeatherSystem::kRainStarts)
		static constexpr double CoreBaseM = 750.0;
		static constexpr double CoreTopM = 6500.0;   // drawn to 6.5 km: from on the lake the base and lower body are what show,
		                                             // and a shallower layer keeps the tracer's samples dense
		static constexpr double AnvilBaseM = 4800.0;
		static constexpr double AnvilAheadM = 9000.0;
		// W8 (storm from the sunshine): the anvil thins as the square of its distance ahead (a thin ice veil far out), and
		// ice (crystals tens of microns across) dims the sun a third as much as the water cloud at the same density
		// (extinction 3 IWC / 2 rho r: about 3e-3 /m for 0.1 g/m^3 at 50 um, against 1e-2 for the deck), so the sun reaches
		// the water under the forward anvil until the shelf and the core are close.
		static constexpr double AnvilIceExtinction = 0.3;
		// The sky's gloom (CloudDarkness) builds as the shelf covers it overhead: none 3 km ahead, all 300 m behind the front.
		static constexpr double OverheadFarM = 3000.0;
		static constexpr double OverheadNearM = -300.0;
		// Cumulus ahead of the front fade from 5 km out and are gone 1.5 km out (towers flat grey in the deck's shade).
		static constexpr double CumulusFadeFarM = 5000.0;
		static constexpr double CumulusFadeNearM = 1500.0;
		// The shelf's leading edge is crisp (the arcus): density rises from nothing to full in this many metres back.
		static constexpr double ShelfEdgeM = 60.0;
		// Its rolled front face, this deep behind the lip, is lit and pale; the underside behind it dark.
		static constexpr double ShelfFaceM = 450.0;

		/** Storm cloud density (0..1, before noise) at a distance ahead of the front and an altitude (m). Mask is the
		 *  storm's lateral extent along the front (the weather map's storm channel), Build its growth (0..1). */
		static double Density(double DistanceAheadM, double AltitudeM, double Mask, double Build);
		/** W5a: the shelf face's run X (m behind the lip) as a smooth staircase, flat at each tier, even after the third. */
		static double TierX(double X);
		/** Where the shelf cloud's leading edge is (m ahead of the front). */
		static double LeadingEdgeAhead() { return ShelfLeadM; }
		/** W8: the anvil's density alone (thin ice cloud, part of Density). */
		static double AnvilDensity(double DistanceAheadM, double AltitudeM, double Build);
		/** W8: how much of the storm's gloom is overhead at a point D metres ahead of the front (0..1). */
		static double Overhead(double DistanceAheadM);
		/** W8: what is left of the fair cumulus (0..1) D metres ahead of the front (gone near and under the storm). */
		static double CumulusFade(double DistanceAheadM, double Build);
		/** W8: the shelf's shading as the material draws it (albedo times occlusion, 0..1): X metres behind the lip, H the
		 *  height up its face (0 base .. 1 top). The rolled front face is pale, the underside dark. */
		static double ShelfShade(double X, double H);
	};

	/**
	 * A weather map: what the volumetric clouds are made of, painted from the weather state over a square around the
	 * camera. RGBA per texel: cumulus, stratus and cirrus presence (0..1; each layer's mean over the map is its coverage),
	 * and the storm's lateral extent. Texture rows run north (X), columns east (Y).
	 */
	class SAILINGPHYSICS_API FWeatherMap
	{
	public:
		static constexpr int N = 1024;   // Graphics G1: 62.5 m texels (was 256: 250 m cells read as blocks)
		static constexpr double SizeMeters = 64000.0;

		/** Land fraction (0 water .. 1 land) at a map point, optional: cumulus build over the land on a summer day. */
		std::function<double(double X, double Y)> LandFraction;

		/** Paints the map around a world point at weather time T. The map lies in the clouds' drifting frame: OriginX/Y
		 *  are field coordinates, and world = field + Drift * T. */
		void Paint(const FCloudSky& Sky, const FGustFront& Front, double CenterX, double CenterY, double T);

		/**
		 * How much direct sun reaches a point on the water (0..1): the transmittance along the ray toward the sun through
		 * the layers (their presence in this map, profiles and an average extinction) and the storm (FStormShape). The
		 * scene's sunlight follows the clouds overhead, so a cumulus shadow or the shelf cloud's arrival darkens the lake.
		 * FrontTravelM: how far the gust front has moved (m); SunX/Y/Z: unit vector toward the sun (map frame).
		 */
		double SunTransmittance(const FCloudSky& Sky, const FGustFront& Front, double FrontTravelM, double DriftT, double X, double Y,
			double SunX, double SunY, double SunZ) const;
		double OriginX() const { return X0; }
		double OriginY() const { return Y0; }
		const std::vector<float>& Pixels() const { return Rgba; }
		/** Mean of one channel (0 cumulus, 1 stratus, 2 cirrus, 3 storm). */
		double Mean(int Channel) const;

	private:
		double X0 = 0.0, Y0 = 0.0;
		std::vector<float> Rgba;
	};
}
