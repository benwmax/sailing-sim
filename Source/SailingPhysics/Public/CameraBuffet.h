#pragma once

#include "SailingPhysicsApi.h"

namespace Sailing
{
	/** What the boat does to the camera this frame (Storm look, docs/storm-look/camera-buffet/). */
	struct FCameraBuffetInput
	{
		double Dt = 0.0;               // s
		double Time = 0.0;             // s, the world clock (the tremble's phase)
		double SlamClosingMs = 0.0;    // how fast the water closes on her bow while it is in it (m/s; 0 out of it)
		double GreenWaterM = 0.0;      // water over her rail (FGreenWater::DepthM)
		double ApparentWindMs = 0.0;   // the wind on the camera
	};

	/**
	 * Storm look (docs/storm-look/camera-buffet/): the camera's buffet in a blow, the way a camera on a boat takes it. A hard
	 * slam (the water closing on the bow at over 1.2 m/s, AWaterSurface::UpdateSpray's splash) and a sea coming aboard kick
	 * it: a quick judder (7 Hz, gone in about a third of a second) over a slower lurch (1.6 Hz, about a second), a few
	 * centimetres and a degree or two at the hardest; strong apparent wind past about 22 kn makes it tremble a little.
	 * Each kick fires on the rising edge of its event, so a bow held in a wave kicks once. Plain logic, no randomness: the
	 * tremble is a sum of sines of the clock. The pawn applies it to the chase and cockpit views when Settings > Camera
	 * shake is on (never in photo mode, the capture mode or a measured run).
	 */
	class SAILINGPHYSICS_API FCameraBuffet
	{
	public:
		static constexpr double SlamThresholdMs = 1.2;
		static constexpr double GreenWaterThresholdM = 0.03;
		static constexpr double TrembleFromMs = 11.0;

		void Step(const FCameraBuffetInput& In);
		/** A kick of a strength 0..1 (the events above call it; tests too). */
		void Kick(double Strength);
		void Reset();

		// The shake: camera frame offset (m: x forward, y right, z up) and turns (degrees).
		double OffsetX = 0.0, OffsetY = 0.0, OffsetZ = 0.0;
		double PitchDeg = 0.0, YawDeg = 0.0, RollDeg = 0.0;

		/** The kicks' energy left (0..1+), for tests and the debug line. */
		double Energy() const { return Judder + Lurch; }

	private:
		double Judder = 0.0, Lurch = 0.0;    // envelopes
		double JudderPhase = 0.0, LurchPhase = 0.0;
		double KickSide = 1.0;               // alternates, so successive kicks don't all lurch one way
		bool bSlamWasOn = false, bGreenWasOn = false;
	};
}
