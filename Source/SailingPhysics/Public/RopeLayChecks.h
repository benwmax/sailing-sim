#pragma once

#include "SailingPhysicsApi.h"
#include <string>
#include <vector>

namespace Sailing
{
	/**
	 * docs/rope-lay/: the rope lay's checks (RopeLay.h), shared by the automation tests (SailingSim.Visual.RopeLay.*) and the
	 * standalone tool (scripts/rope-check.sh). They lay a jib sheet over a model cabin trunk (the plan's figure: a 3.3 m lazy
	 * sheet from a high clew over a trunk 70 cm tall onto the side deck), a free line, a sheet round a block and onto a
	 * winch, and say what they measured.
	 */
	struct FRopeLayCheck
	{
		std::string Name;
		bool bPass = false;
		std::vector<std::string> Lines;
	};

	namespace RopeLayChecks
	{
		/** A line that touches nothing is today's free curve exactly (rings on the parabola within 0.1 mm) and its drawn
		 *  length is the line's (chord x (1 + slack)) within 2%. */
		SAILINGPHYSICS_API FRopeLayCheck FreeLine();
		/** The lazy sheet over the trunk: no ring or span inside it (its centre past a third of its radius under the surface), every ring over the roof resting on it (within
		 *  1 cm, not floating), no step between neighbouring rings steeper than 1.5 to 1, no bend tighter than two diameters
		 *  between its ends, rings packed at the roof's edges (under 60% of the mean spacing). */
		SAILINGPHYSICS_API FRopeLayCheck DrapeOverTrunk();
		/** The clew moved a millimetre at a time over 3 cm: the drawn rope never jumps (each new ring within 3 mm of the last
		 *  frame's rope), where today's 2 cm lift steps flicked. */
		SAILINGPHYSICS_API FRopeLayCheck NoShimmer();
		/** The same inputs give the same rings to the bit. */
		SAILINGPHYSICS_API FRopeLayCheck Deterministic();
		/** A sheet round a lead block bends on a curve (no vertex turns more than a third of the whole turn) and meets the
		 *  block's neighbours on their tangents. */
		SAILINGPHYSICS_API FRopeLayCheck BlockTangent();
		/** On a winch: in on the drum's tangent (1 deg) from either side of the boat, three turns clockwise seen from above,
		 *  on the drum's radius, rising. */
		SAILINGPHYSICS_API FRopeLayCheck WinchTurns();

		/** 2,592 lays round the trunk (clews and leads all about it, taut to lazy): every ring finite, no ring or span's centre
		 *  inside the trunk past a third of the rope's radius (the shortest way out). */
		SAILINGPHYSICS_API FRopeLayCheck ManyCases();

		/** About 2,500 lays of a sheet under and over a sailor sitting on it (back leaning and hiking over it, shoulders,
		 *  head, arms to the knees): the rope's centre never more than its radius and a bend's dip into the body. */
		SAILINGPHYSICS_API FRopeLayCheck OverASailor();
		/** 432 lays of a mainsheet across a lifeline's two wires (the Mac's RigClearance: a Catalina 22's through one): no point
		 *  of the rope in one, looked at every millimetre. */
		SAILINGPHYSICS_API FRopeLayCheck OverALifeline();

		SAILINGPHYSICS_API std::vector<FRopeLayCheck> All();
	}
}
