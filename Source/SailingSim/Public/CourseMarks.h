#pragma once

#include "CoreMinimal.h"

class UStaticMesh;

/**
 * The course marks and the crew-overboard buoy (part detail loop, docs/part-detail-loop/marks.md): kit meshes built by
 * Tools/boatkit/bk_part_marks.py and imported with the rest of the kit to /Game/Boats/Kit (SM_Kit_RaceMark,
 * SM_Kit_LessonMark, SM_Kit_PinBuoy, SM_Kit_HorseshoeBuoy, SM_Kit_MOBBuoy). Their origin is on the waterline and they carry their own
 * MI_Kit_* materials, so they are placed at the water's height at scale 1 with no colour override.
 */
namespace CourseMarks
{
	/** The kit mesh SM_Kit_<Part>, or null when the kit hasn't been imported with it yet (callers keep the engine
	 *  shape then). Checks the package first, so a missing mesh doesn't log a load warning. */
	SAILINGSIM_API UStaticMesh* Load(const TCHAR* Part);
}
