#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"

#include <cstdint>
#include <string>
#include <vector>

namespace Sailing
{
	/**
	 * Walking a ship (docs/ship-walk/): the frigate's decks as a walker sees them. Everything is in the ship's frame
	 * (metres, X forward, Y starboard, Z up, the model's origin), so the walker rides the ship however she rolls and the
	 * game only puts the ship's transform on top. No physics engine collision: a baked walk map (Tools/shipkit/frigate/
	 * walk.py, `Content/TerrainData/Ships/<Ship>.walk`) holds each deck's floor and what is overhead on a grid, and the
	 * ladders between the decks.
	 */

	/** One deck's floor on a grid in plan (cell (i, j) is centred at X0 + i Cell, Y0 + j Cell). */
	struct SAILINGPHYSICS_API FWalkDeck
	{
		std::string Name;                  // "Spar", "Gun", "Berth", "Orlop", "Hold"
		double X0 = 0.0, Y0 = 0.0, Cell = 0.1;
		int NX = 0, NY = 0;
		std::vector<float> Floor;          // ship Z of the floor's top (m); NaN where there is none (a hatch, the side, a gun)
		std::vector<float> Overhead;       // ship Z of the lowest thing over the floor (a beam's underside); +inf in the open
		std::vector<uint8_t> Stand;        // 1 where a walker's body fits (FWalkMap::Finish)
		uint32_t AlsoLoad = 0;             // decks to keep loaded while on this one (seen through the waist, a grating)

		int Index(int I, int J) const { return J * NX + I; }
		bool InGrid(int I, int J) const { return I >= 0 && J >= 0 && I < NX && J < NY; }
		/** The nearest cell to a point (may be outside the grid). */
		void CellOf(double X, double Y, int& I, int& J) const;
		/** The floor's height at a point, bilinear between the cells that have a floor within a step of each other; NaN
		 *  where the nearest cell has none. */
		double FloorAt(double X, double Y) const;
		/** What is overhead at the nearest cell (+inf in the open or off the grid). */
		double OverheadAt(double X, double Y) const;
		/** A walker can stand here (the nearest cell's Stand). */
		bool CanStand(double X, double Y) const;
	};

	enum class EWalkLink : uint8_t { Ladder, Steps };

	/** A way between two decks: a ladder's foot on the lower deck, its top on the upper (where you step off it). */
	struct SAILINGPHYSICS_API FWalkLink
	{
		EWalkLink Kind = EWalkLink::Ladder;
		int Lower = 0, Upper = 0;          // deck indices
		Vec3 Foot, Top;                    // where a walker stands at each end (ship frame, on the floor)
		double HalfWidth = 0.4;
		std::string Name;

		double Length() const { return (Top - Foot).Length(); }
	};

	/** A named place: "Helm" (where a walker stands at the wheel, facing forward), "Lamp" (a cabin lamp's bulb, lit while
	 *  its deck is shown: Bluebonnet's). */
	struct SAILINGPHYSICS_API FWalkSpot
	{
		std::string Name;
		int Deck = 0;
		double X = 0.0, Y = 0.0, YawDeg = 0.0;   // ship frame; yaw 0 forward, + to starboard
		double Z = 0.0;                           // ship frame (file version 3; 0 in older files)
	};

	struct SAILINGPHYSICS_API FWalkMap
	{
		static constexpr uint32_t Magic = 0x4B4C5753u;   // "SWLK" little-endian
		static constexpr uint32_t Version = 3u;           // 2 added the spots (1 still reads, with none), 3 their height
		static constexpr double BodyRadius = 0.22;       // m: shoulders turned, a sailor's half width
		static constexpr double MaxStep = 0.32;          // m: the most a foot steps up or down (a coaming, a sill)
		static constexpr double MinHeadroom = 1.25;      // m: lower than this he would have to crawl

		std::vector<FWalkDeck> Decks;
		std::vector<FWalkLink> Links;
		std::vector<FWalkSpot> Spots;

		bool IsLoaded() const { return !Decks.empty(); }
		int DeckNamed(const char* Name) const;
		const FWalkSpot* SpotNamed(const char* Name) const;

		/** A helmsman stands this far abaft a double wheel's axle (the midpoint between its wheels): half the 44 in between
		 *  Commonwealth's wheels (0.56 m) and 1.1 m back from the after wheel's plane, where the whole wheel (66 in across,
		 *  its top at 2 m) shows at hand height in the game's wide view. A walk file's "Helm" spot baked nearer than this
		 *  (the first bake's 0.7 m put the eye inside the after wheel's rim; 1.05 m filled the frame with it) stands back
		 *  to it: HelmStandX. */
		static constexpr double HelmAbaftWheelAxle = 1.65;
		/** Where the helmsman stands along the ship for a Helm spot at SpotX and a wheel whose axle midpoint is at WheelX
		 *  (ship frame, +X forward): the spot itself, unless it is forward of HelmAbaftWheelAxle abaft the axle. */
		static double HelmStandX(double SpotX, double WheelX);

		/**
		 * Reads a walk file's bytes (the format is written by walk.py; little-endian):
		 *   u32 magic "SWLK", u32 version, u32 decks, u32 links
		 *   per deck: u8 name length, name, f64 X0, Y0, Cell, BaseZ, i32 NX, NY, u32 AlsoLoad,
		 *             i16 floor[NX NY] (mm over BaseZ; -32768 none), i16 overhead[NX NY] (mm over BaseZ; 32767 open)
		 *   per link: u8 kind, u8 lower, u8 upper, u8 name length, name, f64 foot xyz, top xyz, half width
		 *   (version 2) u32 spots; per spot: u8 deck, u8 name length, name, f64 x, y, yaw deg
		 * then Finish(). False (and Error set) on anything malformed; the map is left empty.
		 */
		bool Parse(const uint8_t* Bytes, size_t Size, std::string* Error = nullptr);
		/** The bytes Parse reads (tests build maps in code and round-trip them). */
		std::vector<uint8_t> Write() const;
		/** Marks where a walker fits: a floor, headroom, and every floor within BodyRadius no more than MaxStep away. */
		void Finish();
	};

	/** One frame's input to the walker (the game's stick or keys, already in the walker's own terms). */
	struct FWalkInput
	{
		double Forward = 0.0, Right = 0.0;   // -1..1: move relative to where he faces; on a ladder Forward carries on the way he got on
		double LookYawDeg = 0.0, LookPitchDeg = 0.0;   // this frame's turn of the head
		bool bRun = false, bCrouch = false;
		bool bUse = false;                   // a press: take the ladder in front of you
	};

	/**
	 * The walker: feet on a deck, or on a ladder between two. Step it at the frame rate with the felt gravity in the ship's
	 * frame (FBoatTelemetry's, or (0, 0, -g) rotated by her heel and pitch): he walks slower uphill across a heeled deck and
	 * faster down it, and past a slope no shoes hold he slides. His eye drops under low beams and in a crouch.
	 */
	class SAILINGPHYSICS_API FShipWalker
	{
	public:
		static constexpr double WalkSpeed = 1.4;          // m/s
		static constexpr double RunSpeed = 3.0;
		static constexpr double CrouchSpeed = 0.8;
		static constexpr double DuckSpeed = 1.0;          // under a beam
		static constexpr double Accel = 6.0;              // m/s^2 to change speed on deck
		static constexpr double ClimbSpeed = 0.8;         // m/s along a ladder (hand over hand, briskly)
		static constexpr double EyeStand = 1.62;          // m over the floor
		static constexpr double EyeCrouch = 1.15;
		static constexpr double EyeLowest = 0.9;
		static constexpr double LadderEyeLowest = 0.3;   // m over the feet: on a ladder through a hatch the head bows lower
		static constexpr double LadderKnee = 0.5;        // m: on a ladder, only what is higher over the feet bows the head
		static constexpr double HeadOverEye = 0.14;       // m: the crown and a little room over the eye
		static constexpr double EyeTau = 0.12;            // s: the eye eases to its height
		static constexpr double GripSlopeDeg = 24.0;      // a slope past which he slides (a wet deck, bare feet)
		static constexpr double MountRange = 0.6;         // m from a ladder's end to take it
		static constexpr double MaxSlide = 3.0;           // m/s: the fastest he slides
		static constexpr double SlideStop = 4.0;          // m/s^2: his feet catching once the slope is back in his grip

		/** Puts him on a deck at a point (moved to the nearest place he fits, within 2 m), facing YawDeg (0 forward, + to
		 *  starboard). False when nowhere near there fits. */
		bool Reset(const FWalkMap& Map, int Deck, double X, double Y, double YawDeg);
		void Step(const FWalkMap& Map, const FWalkInput& In, const Vec3& FeltGravityShip, double Dt);

		int GetDeck() const { return Deck; }
		/** The ladder he is on (-1 on a deck) and how far up it, 0 foot .. 1 top. */
		int GetLink() const { return Link; }
		double GetLinkT() const { return LinkT; }
		Vec3 GetFeet() const { return Feet; }
		Vec3 GetVelocity() const { return Vel + Slide; }
		double GetEyeHeight() const { return Eye; }
		Vec3 GetEye() const { return { Feet.X, Feet.Y, Feet.Z + Eye }; }
		double GetYawDeg() const { return YawDeg; }
		double GetPitchDeg() const { return PitchDeg; }
		/** His eye is held down by something overhead. */
		bool IsDucking() const { return bDucking; }
		bool IsSliding() const { return bSliding; }
		/** A ladder end within reach (for the HUD's prompt), -1 if none. */
		int LinkInReach(const FWalkMap& Map) const;
		/** Decks to have loaded (bit per deck): his, any a ladder within NearM leads to, both ends of his ladder, and the
		 *  decks his deck's AlsoLoad names. */
		uint32_t DecksWanted(const FWalkMap& Map, double NearM = 6.0) const;
		/** The deck over each deck DecksWanted names (bit per deck; a map's decks run top to bottom): its planks are
		 *  their overhead, so it is shown with them, but it is not lived on, so its lamps stay unlit (unshadowed, they
		 *  would light down through its planks). */
		uint32_t DecksOverhead(const FWalkMap& Map, double NearM = 6.0) const;

	private:
		bool TryMove(const FWalkDeck& D, double Dx, double Dy);
		bool MountFacing(const FWalkMap& Map, double MoveX, double MoveY, bool bUse);
		void SettleEye(const FWalkMap& Map, double Target, double Dt);

		int Deck = 0, Link = -1;
		double LinkT = 0.0;
		double ClimbSign = 1.0;            // +1 got on at the foot (Forward climbs), -1 at the top (Forward goes down)
		double MountCooldown = 0.0;        // s after stepping off a ladder before another is taken
		Vec3 Feet, Vel, Slide;
		double Eye = EyeStand;
		double YawDeg = 0.0, PitchDeg = 0.0;
		bool bDucking = false, bSliding = false;
	};
}
