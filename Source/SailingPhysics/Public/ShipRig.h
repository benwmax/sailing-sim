#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"

#include <cstdint>

namespace Sailing
{
	/**
	 * A ship's rig as the model shows it (docs/ship-rig/): the spars that move (yards bracing and hoisting, the spanker's
	 * boom and gaff) and which of each sail's states is shown (set, clewed up, furled; the fore-and-aft sails mirrored on
	 * the starboard tack). Plain logic: the physics gives the yards' angles and how much of each sail is out
	 * (FBoatState::YardAngle, SquareOut, MainOut...), FShipRigPose turns them into each spar's motion in the ship frame
	 * (metres, X forward, Y starboard, Z up) and each sail's shown state, and the game puts those on the model's parts.
	 * The table is the model build's rig.json and sails.json (Tools/shipkit/frigate/rig_table.py).
	 */
	constexpr int kMaxRigSpars = 16;
	constexpr int kMaxRigSails = 24;
	constexpr int kMaxRigSquare = 12;     // FBoatState's square sails (kMaxSquareSails)
	constexpr int kMaxRigRows = 40;
	constexpr int kMaxRigHoistRows = 8;

	/** What turns a spar: a square sail's yard angle (its own, or the one it braces with), the main boom, or nothing. */
	enum class ERigSparDrive : uint8_t { Square, Boom, Fixed };
	enum class ERigSailKind : uint8_t { Square, Headsail, Staysail, Spanker };
	/** The sail's object shown (the Head is shown in every state). */
	enum class ESailShown : uint8_t { Set, Clewed, Furled };

	struct FRigRow { double Deg; double Metres; };

	/** A moving spar. Its turn is about Axis through Origin, right-handed (+ swings a square yard's starboard arm aft and
	 *  the boom and gaff to port); hoisting moves it along Axis (the model hangs it hoisted). */
	struct FRigSpar
	{
		const char* Name;
		Vec3 Origin;
		Vec3 Axis;
		double HoistLowered;          // m along the axis, lowered (0 hoisted)
		double BraceLo, BraceHi;      // deg, hoisted
		int NumBraceByHoist;
		double BraceByHoist[kMaxRigHoistRows][3]; // [hoist 0..1, lo, hi]: between two rows take the narrower
		int NumEase;                  // how far the truss or parrel lets it come forward as it braces (deg -> m), hoisted
		FRigRow Ease[kMaxRigRows];
		int NumEaseLowered;           // the same, lowered
		FRigRow EaseLowered[kMaxRigRows];
		ERigSparDrive Drive;
		int Square;                   // the physics' square sail whose yard angle turns it (Drive Square)
	};

	struct FRigSail
	{
		const char* Name;
		int Spar;                     // the spar it rides on, or -1 (the ship)
		ERigSailKind Kind;
		int Square;                   // the physics' square sail, or -1
		const char* Head;             // "" if none
		const char* Set;
		const char* Clewed;
		const char* Furled;
		bool bMirror;                 // the starboard tack is the Set mirrored about this plane (ship frame, at rest)
		Vec3 MirrorPoint;
		Vec3 MirrorNormal;
		double SetBraceLo, SetBraceHi; // deg: its yard's limits with this sail set (0, 0 = the spar's)
		int NumSetEase;
		FRigRow SetEase[kMaxRigRows];
	};

	struct FShipRigData
	{
		const FRigSpar* Spars = nullptr;
		int NumSpars = 0;
		const FRigSail* Sails = nullptr;
		int NumSails = 0;

		int SailOnSpar(int Spar) const;   // the sail riding on a spar whose yard limits apply (-1 none)
		int SparNamed(const char* Name) const;
		int SailNamed(const char* Name) const;
	};

	/** The rig of a ship by its config name ("Commonwealth"), or nullptr. */
	SAILINGPHYSICS_API const FShipRigData* ShipRigFor(const char* ConfigName);
	SAILINGPHYSICS_API const FShipRigData& CommonwealthRig();

	/** A rigid motion (or a mirror) in the ship frame: P' = M P + T. */
	struct SAILINGPHYSICS_API FRigMotion
	{
		double M[3][3] = { { 1, 0, 0 }, { 0, 1, 0 }, { 0, 0, 1 } };
		Vec3 T;

		Vec3 Apply(const Vec3& P) const;
		Vec3 ApplyVector(const Vec3& V) const;
		/** This after B (B first). */
		FRigMotion operator*(const FRigMotion& B) const;
		double Determinant() const;
	};

	/** The table's linear interpolation (clamped at its ends); 0 for an empty table. */
	SAILINGPHYSICS_API double RigTableAt(const FRigRow* Rows, int Num, double Deg);
	/** The spar's brace limits at a hoist (0 lowered, 1 hoisted), narrowed by a set sail's own (Sail -1 for none). */
	SAILINGPHYSICS_API void RigBraceLimits(const FShipRigData& Rig, int Spar, double Hoist, int Sail, double& OutLo, double& OutHi);
	/** How far forward the spar comes at a turn and hoist (a set sail's own table where it has one). */
	SAILINGPHYSICS_API double RigEase(const FShipRigData& Rig, int Spar, double Hoist, int Sail, double TurnDeg);
	/** A spar's motion from its rest (hoisted, square): lowered by (1 - Hoist) of its travel, eased forward along its own
	 *  X, then turned about its axis. */
	SAILINGPHYSICS_API FRigMotion RigSparMotion(const FRigSpar& Spar, double Hoist, double EaseM, double TurnDeg);
	/** The mirror about a sail's starboard-tack plane (identity if it has none). */
	SAILINGPHYSICS_API FRigMotion RigSailMirror(const FRigSail& Sail);

	/** What the rig answers to: the physics' state, plus whether the crew want each sail furled (not just clewed up). */
	struct SAILINGPHYSICS_API FShipRigInput
	{
		double YardAngle[kMaxRigSquare] = {};   // rad, + = starboard yardarm forward (FBoatState)
		double SquareOut[kMaxRigSquare] = {};   // 0 clewed up or furled .. 1 drawing
		bool bSquareFurl[kMaxRigSquare] = {};   // the control asks it furled
		double BoomAngle = 0.0;                 // rad, + = boom to starboard
		double MainOut = 1.0, JibOut = 1.0, StaysailOut = 1.0;
		int MainSide = 1, JibSide = 1, StaysailSide = 1; // the side the sail lies on (+1 starboard: the port tack)
	};

	/**
	 * The rig's pose: each spar's hoist (moving at the crew's pace), turn and ease, each sail's shown state and tack.
	 * Reset puts every spar hoisted and square and every sail set on the port tack.
	 */
	class SAILINGPHYSICS_API FShipRigPose
	{
	public:
		/** Seconds to hoist or lower a yard its whole travel. */
		static constexpr double HoistSeconds = 30.0;
		/** A sail shows set from this much out. */
		static constexpr double SetFrom = 0.5;
		/** A sail asked furled shows furled from this little out (and, for a yard that lowers, once it is down). */
		static constexpr double FurledUnder = 0.02;

		void Reset(const FShipRigData& Rig);
		void Update(const FShipRigData& Rig, const FShipRigInput& In, double Dt);

		double GetHoist(int Spar) const { return Hoist[Spar]; }
		double GetTurnDeg(int Spar) const { return TurnDeg[Spar]; }
		double GetEase(int Spar) const { return Ease[Spar]; }
		ESailShown GetShown(int Sail) const { return Shown[Sail]; }
		bool IsMirrored(int Sail) const { return bMirrored[Sail]; }
		/** The spar's motion from rest (ship frame). */
		FRigMotion SparMotion(const FShipRigData& Rig, int Spar) const;
		/** Where a sail's object is drawn from its rest: its spar's motion after the mirror when mirrored. */
		FRigMotion SailMotion(const FShipRigData& Rig, int Sail) const;

	private:
		double Hoist[kMaxRigSpars] = {};
		double TurnDeg[kMaxRigSpars] = {};
		double Ease[kMaxRigSpars] = {};
		ESailShown Shown[kMaxRigSails] = {};
		bool bMirrored[kMaxRigSails] = {};
	};
}
