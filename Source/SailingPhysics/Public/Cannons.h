#pragma once

#include "SailingPhysicsApi.h"
#include "SailingMath.h"
#include "PortableRandom.h"

#include <cstdint>
#include <string>
#include <vector>

/**
 * Cannon fire for the frigate Commonwealth (docs/cannon-fire/): the guns' drill, their recoil, and the smoke and flash a
 * shot leaves. Bean (Nov 15 2026): "it does not need to shoot real ammo. just the effect is enough": nothing flies, but
 * every gun goes through the real drill and recoils as a shotted gun does, and the smoke is the cloud a broadside of
 * black powder leaves. Plain C++ (no Unreal): ACannonBattery (SailingSim) draws it, the tests drive it.
 *
 * Frames. The ship's frame is Unreal's in metres (X forward, Y to starboard, Z up), as the model's guns.json. Each gun
 * stands in its port's frame (guns.json frames_note): origin on the deck at the side's inner face under the port's middle,
 * X out through the port, Z the deck's normal, Y = Z x X. The carriage (a long gun's truck carriage, a carronade's bed)
 * moves along the port's X only. The smoke lives in the map frame (the physics' world frame, metres), so the ship sails
 * out of her own smoke.
 */
namespace Sailing
{
	enum class ECannonKind : uint8_t { Long24, Carronade32 };
	enum class ECannonSide : uint8_t { Port, Starboard, Both };
	enum class ECannonOrder : uint8_t { CastLoose, Load, RunOut, Fire, CeaseFire, Secure };
	enum class ECannonFireMode : uint8_t { Broadside, Ripple, AtWill };

	/**
	 * Where a gun is in its drill. A long gun at sea is Housed (lashed up against the port, the lid shut). Cast loose it is
	 * run in, loaded, run out (lid open first) and Ready. Fired, it recoils to the breeching and is Spent: sponged, loaded and
	 * run out again while the battery is firing, or left run in (loaded or not) when the fire stops. Secure houses it again.
	 * A carronade has no lid and is never housed: Housed means run out and lashed, unloaded.
	 */
	enum class EGunState : uint8_t
	{
		Housed,       // lashed for sea (long gun: hauled out against the sill, breech on the bed, lid shut)
		CastingLoose, // the lashings off, the gun eased in to the loading place
		Waiting,      // run in, unloaded, no order
		Sponging,     // the bore sponged out after a shot
		Loading,      // cartridge, wad, shot, wad, rammed home, primed
		Loaded,       // run in and loaded, waiting for the order to run out
		OpeningLid,   // the lid hauled up (long guns)
		RunningOut,   // the crew hauling her out on the side tackles
		Ready,        // run out, loaded, primed: waiting for the word
		Lock,         // the lanyard pulled: flint, pan, vent, charge
		Recoil,       // flying in against the breeching
		Spent,        // at rest after the recoil, run in, the bore foul
		RunningIn,    // eased in on the train tackle (to secure, or to load a gun that was run out)
		ClosingLid,   // securing: the lid let down
		Securing,     // hauled out against the sill and lashed
		Count
	};

	SAILINGPHYSICS_API const char* GunStateName(EGunState S);

	/** One gun as the model placed it (Tools/shipkit/frigate/cannon_data.py reads the build's guns.json). */
	struct FCannonMount
	{
		ECannonKind Kind = ECannonKind::Long24;
		ECannonSide Side = ECannonSide::Port;    // Port or Starboard
		int32_t Port = 0;                        // the port's number, 1 at the stern
		char Id[8] = { 0 };                      // "P01", "S14"
		// The port's frame in the ship's frame (m; unit axes).
		Vec3 Origin, AxisX = Vec3(1, 0, 0), AxisY = Vec3(0, 1, 0), AxisZ = Vec3(0, 0, 1);
		// The carriage's (or bed's) origin along the port's X in each pose (m): housed for sea, run in (the breeching taut:
		// where the recoil stops and the gun is loaded), run out (fighting).
		double HousedX = 0.0, RunInX = 0.0, RunOutX = 0.0;
		double SlideX = 0.0;               // a carronade's slide (its fighting bolt) along X; its bed rides on it
		double HousedElevationDeg = 0.0;   // the barrel housed (a long gun's breech down on the bed)
		double LidOpenDeg = 0.0;           // 0: no lid (carronades)
		double MinElevationDeg = -1.44, MaxElevationDeg = 10.5;
		// The lid's hinge (ship frame, m): origin on the hinge line, X along it; the lid opens by a turn of LidDeg about +X.
		// bHinge false until the model's guns.json carries it (the lid then stays drawn shut).
		bool bHinge = false;
		Vec3 HingeOrigin, HingeX = Vec3(1, 0, 0), HingeY = Vec3(0, 1, 0), HingeZ = Vec3(0, 0, 1);
	};

	/** The frigate Commonwealth's 50 guns as built (FrigateGunData.inl, from Tools/shipkit/frigate/cannon_data.py). */
	SAILINGPHYSICS_API std::vector<FCannonMount> FrigateCannonMounts();

	/** What each kind of gun is: masses, the barrel's place on its carriage, where its muzzle and vent are. */
	struct SAILINGPHYSICS_API FCannonKindSpec
	{
		double GunKg = 0.0;             // the barrel
		double CarriageKg = 0.0;        // carriage and trucks (long gun) or bed (carronade): what recoils with the barrel
		double ShotKg = 0.0;
		double ChargeKg = 0.0;          // the service charge (a third of the shot's weight for a long gun, a twelfth for a carronade)
		double MuzzleVelocityMs = 0.0;
		double BoreM = 0.0;
		double CarriageZ = 0.0;         // the carriage's origin over the deck (a carronade's bed rides on its slide)
		Vec3 BarrelPivot;               // the trunnions (long gun) or the loop's bolt (carronade) in the carriage's frame
		Vec3 Muzzle;                    // the muzzle's face on the bore in the barrel's frame (X along the bore)
		Vec3 Vent;                      // the vent (touch hole) in the barrel's frame
		Vec3 Pan;                       // the lock's pan
		double FrictionMu = 0.0;        // rolling resistance of the trucks, or the bed sliding on its slide
		double TruckRadiusFore = 0.0, TruckRadiusHind = 0.0;   // 0 for a carronade

		static FCannonKindSpec Make(ECannonKind Kind);
		double RecoilingKg() const { return GunKg + CarriageKg; }
	};

	/**
	 * Every number a tuner may want to move without a rebuild (docs/cannon-fire/tuning.md): the drill's times, the recoil,
	 * the smoke and the flash. Each has a name (Set/Get by it); the game reads overrides from -SailingCannonFx="Key=V,...",
	 * the console (sailing.CannonFx Key V) and Saved/CannonFx.txt (re-read when it changes). The defaults are the period's
	 * drill and black powder's physics, each justified where it is set (Cannons.cpp, FCannonParams's table).
	 */
	struct SAILINGPHYSICS_API FCannonParams
	{
		// The drill (seconds, for a well-drilled crew: the US Navy's 1812 standard was about a round a minute from a long gun).
		double CrewTimeScale = 1.0;      // every crew time times this (game speed: 0.5 is twice as quick)
		double CrewSpread = 0.15;        // each crew's own pace, +- this share (seeded per gun)
		double CastLooseS = 35.0;
		double LidS = 3.0;
		double SpongeS = 14.0;
		double LoadS = 24.0;             // cartridge, wad, shot, wad, rammed home, pricked and primed
		double RunOutLongS = 12.0;
		double RunOutCarronadeS = 5.0;
		double RunOutUphill = 2.5;       // a gun run out uphill (the weather side heeled) takes 1 + this x sin(slope) longer
		double SecureS = 45.0;
		double PointS = 3.0;             // at will: the captain's pointing before he fires
		// Firing.
		double LockDelayS = 0.11;        // lanyard to the charge going off: flint, pan, vent
		double LockSpreadS = 0.04;
		double BroadsideSpreadS = 0.3;   // a broadside on the word: each captain's lanyard within this
		double RippleIntervalS = 0.45;   // ripple: gun after gun from forward
		double MisfireChance = 0.02;     // a flash in the pan: the pan burns, the gun does not fire; primed again
		double ReprimeS = 6.0;
		// The recoil.
		double GasFactor = 1.5;          // the powder gas's momentum as the charge's mass times this times the muzzle velocity
		double RecoilScale = 1.0;        // every gun's recoil impulse times this (tuning only)
		double RollMu = 0.08;            // the trucks on the deck (a long gun)
		double SlideMu = 0.3;            // the bed on its slide (a carronade)
		double BreechingStretchM = 0.12; // how far the breeching gives when it brings up a full recoil
		double BreechingDamping = 0.5;   // the breeching's damping ratio (a hemp rope's loss)
		// The smoke: a black-powder charge leaves 55% of its mass as solid smoke (potassium carbonate, sulphate, sulphide).
		double SmokePerChargeKg = 0.55;
		double SmokeExtinction = 500.0;  // m^2 per kg of smoke (black powder smoke measures 1,000-3,000: kept lower so a broadside thins in a minute or two)
		double SmokeOpacityCap = 0.85;   // the most one puff hides (overlap gives the depth)
		int32_t PuffsLong = 18;          // puffs per shot from a long gun's muzzle
		int32_t PuffsCarronade = 12;
		int32_t PuffsVent = 2;           // from the vent and pan
		double JetSpeedMs = 75.0;        // the blast's leading puff
		double JetSpreadDeg = 10.0;
		double JetDecayS = 0.22;         // the jet's speed relaxes to the wind's in about this
		double RingShare = 0.3;          // the share of a shot's puffs thrown out round the muzzle (the blast's ring)
		double SigmaStartM = 0.5;        // a puff's size at the muzzle (Gaussian sigma)
		double Diffusivity = 0.1;        // m^2/s, the eddy diffusivity at sigma 1 m (~2 m^2/s at 10 m: the sea breeze's surface layer)
		double DiffusivityPower = 1.333; // grows as sigma^(4/3) (Richardson): bigger puffs spread faster
		double BuoyancyMs2 = 1.2;        // the hot smoke's lift at first
		double BuoyancyDecayS = 2.0;     // cooling: the lift falls off in about this (a broadside's cloud settles 5-10 m up)
		double WindTakeS = 1.5;          // a still puff takes the wind's speed in about this
		double SmokeMaxAgeS = 180.0;
		double MinPuffOpacity = 0.006;   // fainter than this: gone
		double WaterLift = 0.4;          // keeps a puff's centre this many sigmas off the water
		// The flash.
		double FlashS = 0.075;           // the flame's whole life (primary flash and the secondary burning in the air)
		double FlashLengthPerCbrtKg = 2.3;   // m of flame per cube root of the charge (kg): ~3.5 m for a long 24
		double FlashGlowM = 9.0;         // the smoke lit by a flash within this
		double FlashLightCd = 300000.0;  // the light's peak (candela)
		double FlashLightRadiusM = 70.0;
		double PanFlashS = 0.05;
		int32_t Sparks = 20;             // burning grains thrown out with the flame
		double SparkSpeedMs = 55.0;
		double SparkLifeS = 0.35;

		/** Set a parameter by name (case-insensitive). False for an unknown name. */
		bool Set(const std::string& Key, double Value);
		bool Get(const std::string& Key, double& Value) const;
		/** "Key=V,Key=V" or one per line ('#' comments); returns the number applied and lists unknown keys in Unknown. */
		int32_t ApplyOverrides(const std::string& Text, std::string* Unknown = nullptr);
		/** Every parameter, one "Key = value  # what it is" line each (the file a tuner starts from). */
		std::string Dump() const;
		/** The names, in order. */
		static std::vector<std::string> Names();
	};

	/** A gun as it is now. */
	struct SAILINGPHYSICS_API FGun
	{
		FCannonMount Mount;
		EGunState State = EGunState::Housed;
		double StateT = 0.0;            // s in this state
		double StateDuration = 0.0;     // s this state lasts (the crew's), 0 for a state that waits
		double X = 0.0;                 // the carriage's (bed's) place along the port's X (m)
		double V = 0.0;                 // its speed along X (m/s)
		double MoveFrom = 0.0;          // a crewed move's start (run out, ease in, secure)
		double ElevationDeg = 0.0;
		double LidDeg = 0.0;            // the lid's turn (0 shut)
		double TruckTurn = 0.0;         // the trucks' turn (radians, the fore trucks; the hind turn by the radius ratio)
		double Pace = 1.0;              // this crew's pace (times the drill's times)
		double FireAt = -1.0;           // a fire order: the sim time the lanyard is pulled (< 0 none)
		double RestT = 0.0;             // the recoil: how long it has been nearly still
		bool bLoaded = false;
		bool bFiring = false;           // keep the drill going (reload and run out) after a shot
		bool bMisfired = false;
		int32_t Shots = 0;
		uint64_t Seed = 0;

		/** The port's frame point (m, ship frame) of a point in the carriage's frame. */
		Vec3 CarriageToShip(const Vec3& P, double CarriageZ) const;
		/** The barrel's frame point (m, ship frame), given the kind. */
		Vec3 BarrelToShip(const Vec3& P, const FCannonKindSpec& K) const;
		/** The bore's direction (ship frame). */
		Vec3 BoreDir() const;
	};

	/** A shot fired this step (for the effects, the sound, the camera and the ship's heel). */
	struct FCannonShot
	{
		int32_t Gun = -1;
		double Time = 0.0;
		Vec3 MuzzleShip;                // ship frame (m)
		Vec3 BoreShip;                  // unit, ship frame
		double ChargeKg = 0.0;
		double ImpulseNs = 0.0;         // the recoil impulse along -bore
		bool bMisfire = false;          // a flash in the pan only
	};

	/** The world the battery needs each step: where the ship is and the gravity she feels. */
	struct FCannonStepInput
	{
		double Dt = 0.0;
		double Time = 0.0;
		Vec3 GravityShip = Vec3(0, 0, -9.81);   // gravity (and the ship's acceleration, as felt) in the ship's frame
	};

	/** Counts for the orders panel. */
	struct FCannonSideStatus
	{
		int32_t Guns = 0;
		int32_t ByState[int32_t(EGunState::Count)] = { 0 };
		int32_t Ready = 0;              // run out and loaded
		int32_t Loaded = 0;             // loaded, in or out
		double NextReadyS = -1.0;       // until the next gun is ready (< 0: none coming)
		int32_t Shots = 0;
	};

	/**
	 * The guns of one ship and their drill. Orders go to a side (or both); the crews do the rest at their own pace. Step
	 * advances every gun (sub-stepped through a recoil, so the breeching's stiffness stays stable) and lists the shots fired
	 * and the force the guns put on the ship (friction and breeching as they recoil: the heel's kick away from the side
	 * that fired). Deterministic for a seed.
	 */
	class SAILINGPHYSICS_API FCannonBattery
	{
	public:
		void Init(const std::vector<FCannonMount>& Mounts, uint64_t Seed = 1);
		void SetParams(const FCannonParams& P) { Params = P; UpdateBreeching(); }
		const FCannonParams& GetParams() const { return Params; }

		void Order(ECannonOrder Order, ECannonSide Side, double Now);
		void SetFireMode(ECannonFireMode Mode) { FireMode = Mode; }
		ECannonFireMode GetFireMode() const { return FireMode; }
		/** Bench and stills: every gun on a side straight to Ready (run out, loaded, lid open), no drill. */
		void MakeReady(ECannonSide Side);

		void Step(const FCannonStepInput& In);

		/** The guns whose lock went off in the last Step (the pan's flash, a tenth of a second before the shot). */
		const std::vector<int32_t>& Locks() const { return StepLocks; }
		/** The shots fired in the last Step. */
		const std::vector<FCannonShot>& Shots() const { return StepShots; }
		/** The guns' force on the ship over the last Step (N, ship frame; mean over the step) and its moment about the ship's origin (N m). */
		const Vec3& ForceOnShip() const { return StepForce; }
		const Vec3& MomentOnShip() const { return StepMoment; }

		const std::vector<FGun>& Guns() const { return GunList; }
		int32_t Num() const { return int32_t(GunList.size()); }
		const FCannonKindSpec& Spec(ECannonKind Kind) const { return Kind == ECannonKind::Long24 ? SpecLong : SpecCarronade; }
		FCannonSideStatus Status(ECannonSide Side) const;

		/** The recoil impulse of one shot (N s): shot plus powder gas. */
		double RecoilImpulse(ECannonKind Kind) const;

	private:
		void Enter(FGun& G, EGunState S, double Duration);
		double CrewTime(const FGun& G, double Base) const { return Base * G.Pace * Params.CrewTimeScale; }
		void StepGun(int32_t Index, FGun& G, const FCannonStepInput& In);
		void Fire(int32_t Index, FGun& G, double Now);
		bool OnSide(const FGun& G, ECannonSide Side) const { return Side == ECannonSide::Both || G.Mount.Side == Side; }
		/** Schedule the side's Ready guns' lanyards for the fire mode (broadside, ripple). */
		void ScheduleVolley(int32_t SideIndex, double Now);
		/** Seconds until a gun reaches Ready by the drill (< 0: not heading there). */
		double ToReady(const FGun& G) const;
		/** How far a side's guns go in the drill (the last order). */
		enum class ETarget : uint8_t { Housed, Loose, Loaded, Out, Firing };
		ETarget TargetFor(const FGun& G) const { return Target[G.Mount.Side == ECannonSide::Starboard ? 1 : 0]; }

		/** The breeching's stiffness and damping for each kind, from the params (a full recoil gives BreechingStretchM). */
		void UpdateBreeching();

		std::vector<FGun> GunList;
		FCannonParams Params;
		double BreechK[2] = { 0.0, 0.0 }, BreechC[2] = { 0.0, 0.0 };   // N/m, N s/m (Long24, Carronade32)
		FCannonKindSpec SpecLong = FCannonKindSpec::Make(ECannonKind::Long24);
		FCannonKindSpec SpecCarronade = FCannonKindSpec::Make(ECannonKind::Carronade32);
		ECannonFireMode FireMode = ECannonFireMode::Broadside;
		FPortableRandom Rng;
		std::vector<FCannonShot> StepShots;
		std::vector<int32_t> StepLocks;
		Vec3 StepForce, StepMoment;
		ETarget Target[2] = { ETarget::Housed, ETarget::Housed };
		bool bVolleyPending[2] = { false, false };   // a broadside or ripple ordered: it goes when the side's guns are ready
	};

	/** The smoke's world: wind and water (the game hands it FWindField and FWaveField, the tests a steady breeze). */
	class SAILINGPHYSICS_API ICannonWorld
	{
	public:
		virtual ~ICannonWorld() = default;
		/** The air's velocity at P (map frame, m/s). */
		virtual Vec3 WindAt(const Vec3& P, double Time) const = 0;
		/** The water's height under (X, Y) (m). */
		virtual double WaterZ(double X, double Y, double Time) const = 0;
	};

	/** One puff of smoke: a Gaussian blob of smoke (mass, centre, size). Drawn as a camera-facing sprite. */
	struct SAILINGPHYSICS_API FSmokePuff
	{
		Vec3 P;                         // centre, map frame (m)
		Vec3 V;                         // velocity (m/s)
		double Sigma = 0.5;             // Gaussian sigma (m)
		double MassKg = 0.0;
		double Age = 0.0;
		double Heat = 1.0;              // its buoyancy left (1 at the muzzle)
		double Glow = 0.0;              // lit by a flash (0..1; decays)
		float Seed = 0.f;               // the sprite's variety
		uint8_t Source = 0;             // 0 muzzle jet, 1 ring, 2 vent

		/** The puff's opacity through its centre: 1 - exp(-tau), tau = kappa m / (2 pi sigma^2), capped. */
		double Opacity(const FCannonParams& Pr) const;
	};

	/** A flash: the flame at a muzzle (or a pan), for its short life. */
	struct SAILINGPHYSICS_API FCannonFlash
	{
		Vec3 P;                         // map frame (m)
		Vec3 Dir;                       // unit, the bore (map frame)
		double Start = 0.0;
		double LengthM = 0.0;
		double Life = 0.0;
		bool bPan = false;
		/** 0..1 brightness at time T: a fast rise and the secondary flash's tail. */
		double Intensity(double T) const;
	};

	/** A burning grain thrown out with the flame. */
	struct FCannonSpark
	{
		Vec3 P, V;
		double Age = 0.0, Life = 0.0;
	};

	/**
	 * The smoke and flame of every shot, in the map frame. Puffs are emitted along the blast's jet (fast, slowing to the
	 * wind's speed in a fraction of a second, which throws the forward plume 15-25 m), round the muzzle (the blast's ring)
	 * and from the vent; then they rise while hot, drift with the wind, and grow by eddy diffusion (sigma^2 grows at 2K, K
	 * growing with sigma^(4/3)), so their opacity falls as the cloud spreads. Over the budget the oldest puffs merge into
	 * their nearest neighbour (mass, momentum and spread kept), so a long action thins and coarsens rather than vanishing.
	 */
	class SAILINGPHYSICS_API FCannonSmoke
	{
	public:
		void SetParams(const FCannonParams& P) { Params = P; }
		void SetBudget(int32_t MaxPuffs) { Budget = MaxPuffs < 16 ? 16 : MaxPuffs; }
		int32_t GetBudget() const { return Budget; }
		void Reseed(uint64_t Seed) { Rng.Reseed(Seed); }

		/**
		 * Emit a shot's smoke and flame. MuzzleMap and BoreMap in the map frame; ShipVelocity is the muzzle's own (the
		 * ship's) velocity, which the smoke starts with.
		 */
		void EmitShot(const Vec3& MuzzleMap, const Vec3& BoreMap, const Vec3& VentMap, const Vec3& ShipVelocity, double ChargeKg,
			bool bMisfire, double Now, bool bLong);

		void Step(double Dt, double Now, const ICannonWorld& World);
		void Clear();

		const std::vector<FSmokePuff>& Puffs() const { return PuffList; }
		const std::vector<FCannonFlash>& Flashes() const { return FlashList; }
		const std::vector<FCannonSpark>& Sparks() const { return SparkList; }
		/** The smoke's whole mass (kg). */
		double TotalMass() const;
		int32_t Merges() const { return MergeCount; }

	private:
		void MergeOldest();
		FCannonParams Params;
		FPortableRandom Rng = FPortableRandom(7);
		int32_t Budget = 1024;
		int32_t MergeCount = 0;
		std::vector<FSmokePuff> PuffList;
		std::vector<FCannonFlash> FlashList;
		std::vector<FCannonSpark> SparkList;
	};

	/** A steady world for the tests and tools: a uniform wind and flat water. */
	class SAILINGPHYSICS_API FSteadyCannonWorld : public ICannonWorld
	{
	public:
		Vec3 Wind;
		double Water = 0.0;
		Vec3 WindAt(const Vec3&, double) const override { return Wind; }
		double WaterZ(double, double, double) const override { return Water; }
	};
}
