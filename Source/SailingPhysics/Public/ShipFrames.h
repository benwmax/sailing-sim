#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"
#include "ShipRig.h"

#include <cstdint>

namespace Sailing
{
	/**
	 * A ship's moving parts (docs/ship-frames/): the tiller under the great cabin's beams turning with the rudder and the
	 * wheel on the quarterdeck turning with it, the six parts of the tiller ropes posed from the build's table by the
	 * helm's degree, the cabin doors swinging for a walker, the capstans' heads. Plain logic in the ship frame (metres, X forward, Y starboard, Z up); the game puts
	 * each motion on the exported part, which sits at its own pivot (the frame's origin and axes) in her frame.
	 * The table is the model build's gundeck.json (Tools/shipkit/frigate/frames_table.py).
	 */
	constexpr int kRopeParts = 6;

	enum class EShipFrameKind : uint8_t { Tiller, Rope, Door, Capstan, Wheel };

	/** A moving part's pivot and axes as built (helm amidships). */
	struct FShipFrame
	{
		const char* Name;
		EShipFrameKind Kind;
		Vec3 Origin;
		Vec3 X, Y, Z;
		double Sign;      // a door: its swing's sign about its own Z (+ right-handed); else 0
		int Rope;         // a rope part: its column in the pose rows; else -1
		bool bBelow;      // exported with the decks below (Decks/), else with the outside model (Outside/)
	};

	/** One rope part's frame at a helm angle: origin, axes as the columns of R (ship = R local), the run's stretch. */
	struct FRopePosePart
	{
		Vec3 O;
		double R[3][3];
		double ScaleX;
	};

	struct FRopePoseRow
	{
		double HelmDeg;
		FRopePosePart Part[kRopeParts];
	};

	struct SAILINGPHYSICS_API FShipFramesData
	{
		const FShipFrame* Frames = nullptr;
		int NumFrames = 0;
		const FRopePoseRow* Poses = nullptr;    // by HelmDeg ascending
		int NumPoses = 0;
		double HardOverDeg = 35.0;              // the tiller's swing each way
		double WheelTurnsHardOver = 2.5;        // the wheel's turns from amidships to hard over
		double DoorOpenDeg = 90.0;

		int FrameNamed(const char* Name) const;
	};

	/** The moving parts of a ship by her config name ("Commonwealth"), or nullptr. */
	SAILINGPHYSICS_API const FShipFramesData* ShipFramesFor(const char* ConfigName);
	SAILINGPHYSICS_API const FShipFramesData& CommonwealthFrames();

	/** The helm's angle (deg, + the tiller to starboard and her head to port, the wheel's sign) from the physics' rudder
	 *  angle (rad, + the bow to starboard), within hard over. */
	SAILINGPHYSICS_API double TillerHelmDeg(const FShipFramesData& Data, double RudderAngleRad);
	/** The wheel's turns from amidships (+ with the helm's sign). */
	SAILINGPHYSICS_API double WheelTurns(const FShipFramesData& Data, double HelmDeg);
	/** A turn of Deg about one of the frame's own axes (0 X, 1 Y, 2 Z) through its origin: the tiller, a door and a
	 *  capstan about Z, the wheel about X (its axle). */
	SAILINGPHYSICS_API FRigMotion FrameTurn(const FShipFrame& Frame, double Deg, int Axis = 2);
	/** A rope part's motion from its rest to its pose at a helm angle (the two nearest whole degrees blended; the run's
	 *  own X stretched). Identity for a part that is not in the table. */
	SAILINGPHYSICS_API FRigMotion RopePartMotion(const FShipFramesData& Data, const FShipFrame& Frame, double HelmDeg);
	/** A walker this near a door's hinge in plan (m) and on its deck (not the one over or under it) wants it open. */
	SAILINGPHYSICS_API bool ShipDoorNear(const FShipFrame& Door, const Vec3& Feet, double WithinM);

	/**
	 * The parts' pose: the helm (the tiller, its ropes and the wheel, WheelTurnsHardOver turns at hard over), the doors
	 * swinging open (a second) for a walker near them and closing when he has gone, the capstans still (no order turns
	 * them yet).
	 */
	class SAILINGPHYSICS_API FShipFramesPose
	{
	public:
		static constexpr double DoorSeconds = 1.0;       // to swing open or shut
		static constexpr double DoorNearM = 1.6;         // a walker this close opens it
		static constexpr double DoorHoldSeconds = 2.0;   // open this long after he has gone
		static constexpr int MaxDoors = 4;

		void Reset(const FShipFramesData& Data);
		/** Feet is the walker's (ship frame), or nullptr when nobody walks her decks. */
		void Update(const FShipFramesData& Data, double RudderAngleRad, const Vec3* Feet, double Dt);

		double GetHelmDeg() const { return HelmDeg; }
		/** A door's opening, 0 shut .. 1 open (by its index among the doors, in the frames' order). */
		double GetDoorOpen(int Door) const { return Door >= 0 && Door < MaxDoors ? DoorOpen[Door] : 0.0; }
		/** A part's motion from its rest (ship frame). */
		FRigMotion Motion(const FShipFramesData& Data, int Frame) const;

	private:
		double HelmDeg = 0.0;
		double DoorOpen[MaxDoors] = {};
		double DoorSince[MaxDoors] = {};   // s since a walker was last near
	};
}
