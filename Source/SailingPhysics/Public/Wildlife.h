#pragma once

#include "SailingPhysicsApi.h"
#include "PortableRandom.h"
#include <cstdint>
#include <functional>
#include <utility>
#include <string>
#include <vector>

namespace Sailing
{
	/**
	 * Wildlife Phase 1 (docs/wildlife-1/README.md): the distant birds. Pure logic on the sim clock, map frame (+X north,
	 * +Y east, metres, Z up from the water), so the tests and Tools/WildlifeCheck run it headless and the game draws it
	 * (AWildlifeActor).
	 *
	 * FWildlifeTable reads a world's Content/TerrainData/<World>.wildlife.json (Tools/wildlife/build_tables.py: seasons
	 * from GBIF sightings, group sizes, habitats, when in the day each animal is about). FWildlifeHabitatMap classes a
	 * window around the camera into the habitats the tables name (open water, offshore, shallows, shore, harbour, cliffs)
	 * from the world's depths and heights. FBirdFlocks keeps the flocks a sailor would see within 2 km: how many of each
	 * bird for the month, the hour and the weather, their flight style (the plan's eight, plus rafts on the water), their
	 * shapes (lines, vees, loose groups, circles) from following the bird ahead, and the birds on the water or the shore
	 * taking off when a boat comes inside their flush distance.
	 */

	/** The plan's flight styles (species.json "styles"), birds only. */
	enum class EBirdStyle : unsigned char
	{
		HeavyGlider,  // pelicans: a few slow beats then a long glide; lines just over the waves, or circling together
		FlapHang,     // gulls: hang in the wind, follow boats, rest on the water
		HoverPlunge,  // terns, osprey, gannets: circle a feeding spot, stall, fold and plunge
		FastLow,      // cormorants, shags: straight lines a metre off the water, rapid beats
		Shearing,     // shearwaters: banked arcs that tip the wave tops on stiff wings
		Soaring,      // vultures, frigatebirds, raptors: circling high with almost no wingbeats
		Wading,       // herons, egrets: stand in the shallows; slow deep beats when flushed
		Insect,       // swallows, martins, swifts: fast jerky zigzags low over the water
		Raft,         // ducks, coots: sit on the water in rafts, flush ahead of the bow
		Count
	};

	SAILINGPHYSICS_API const char* BirdStyleName(EBirdStyle S);
	/** species.json's style key ("heavy_glider", ...) to the style; false for water life (school, jumper, fin, ...). */
	SAILINGPHYSICS_API bool BirdStyleFromKey(const std::string& Key, EBirdStyle& Out);

	enum class EBirdFormation : unsigned char
	{
		Loose,   // each bird on its own slowly wandering offset round the flock's centre
		Line,    // single file, each bird on the path of the one ahead (pelicans, cormorants)
		Vee,     // two arms behind the leader, each bird on the path of the one ahead
		Circle   // each bird on its own circle round the flock's centre (thermals, feeding spots)
	};

	/** Start values from the plan's flight-style table (tune against video; docs/wildlife-1). */
	struct FBirdStyleParams
	{
		double CruiseMs = 10.0;      // level flight through the air
		double BeatHz = 3.0;         // wingbeats a second while flapping
		double FlapSeconds = 1.0;    // a burst of flapping ...
		double GlideSeconds = 0.0;   // ... then a glide (0: never glides)
		double AltMinM = 2.0;        // height over the water while travelling
		double AltMaxM = 10.0;
		double SpacingSpans = 1.5;   // gap to the bird ahead, in wingspans
		EBirdFormation Formation = EBirdFormation::Loose;
		double CircleShare = 0.0;    // share of airborne flocks circling a spot (thermal, feeding) instead of travelling
		double CircleRadiusM = 40.0; // members' circle radius round the centre (spread +-50%)
		double CircleAltM = 60.0;    // circling height
		double TurnRateDeg = 30.0;   // most heading change a second
		double Wander = 0.1;         // 0..1 heading noise (insect hunters zigzag)
		double FlocksPerKm2 = 0.5;   // flocks over 1 km^2 of matching habitat at month weight 1 (start value, tune)
		double RestShare = 0.0;      // share of flocks that start resting (on the water, or standing on the shore)
		double VeeShare = 0.0;       // share of travelling flocks of 6 or more that fly a vee instead of the formation
		double FlushM = 40.0;        // flush distance when the table has none
		double FlightAfterFlushM = 300.0; // flies about this far before it lands again (200 to 400 m)
	};
	SAILINGPHYSICS_API const FBirdStyleParams& BirdStyleParams(EBirdStyle S);

	/** Habitat bits: the tables' habitat words, grouped into what the world's data can tell apart. */
	enum EWildHabitat : uint32_t
	{
		HabOpenWater   = 1u << 0,  // open_water, bay, calm_water, low_over_water: water deeper than 1.5 m
		HabChannel     = 1u << 1,  // passage, channel: water deeper than 6 m (or a world's ship channel)
		HabOffshore    = 1u << 2,  // offshore: water 2 km and more from the shore
		HabFarOffshore = 1u << 3,  // far_offshore: water 5 km and more from the shore, or deeper than 80 m
		HabShallows    = 1u << 4,  // shallows, flats, marsh: water under 1.5 m
		HabShore       = 1u << 5,  // beach, surf, shore, points, coves, islands, jetty, logs, over_shore: within 150 m of the waterline
		HabHarbour     = 1u << 6,  // marina, harbour, docks, boats, perch, roost: inside the world's harbours
		HabCliffs      = 1u << 7,  // cliffs: land 20 m and more above the water within 300 m of it
		HabSky         = 1u << 8,  // sky: anywhere
		HabAll         = 0x1FFu
	};
	/** The tables' habitat words to bits (unknown words are ignored; none known = open water). */
	SAILINGPHYSICS_API uint32_t HabitatBits(const std::vector<std::string>& Words);

	/** One bird row of a world's wildlife table. */
	struct FWildBird
	{
		std::string Id, Name;
		EBirdStyle Style = EBirdStyle::FlapHang;
		double SizeM = 1.0;          // wingspan
		double FlushM = 0.0;         // 0: the style's
		double Months[12] = {};      // the table's monthly weights (0 outside the season)
		uint32_t Habitats = HabOpenWater;
		std::string Activity = "day";
		int GroupTypical = 1, GroupP90 = 1;
		bool bRare = false;
		std::string Water;           // fresh, salt, any
	};

	struct SAILINGPHYSICS_API FWildlifeTable
	{
		std::string World;
		double Box[4] = {};          // lon/lat box the records came from (west, south, east, north)
		std::vector<FWildBird> Birds;
		int OtherAnimals = 0;        // fish, dolphins, turtles, sharks, whales: Phase 2 and on

		/** Reads build_tables.py's JSON; false (with a reason) when it isn't one. */
		bool LoadText(const std::string& Json, std::string* Error = nullptr);
		const FWildBird* Find(const std::string& Id) const;
	};

	/** How active a bird is at this local hour (0..1) for its table activity word, with the sun's elevation. */
	SAILINGPHYSICS_API double ActivityAt(const std::string& Activity, double LocalHour, double SunElevationDeg);

	/** The day's state the birds respond to. */
	struct FWildlifeConditions
	{
		int Month = 6;               // 1..12
		double LocalHour = 12.0;
		double SunElevationDeg = 45.0;
		double RainMmH = 0.0;        // at the camera
		double WindKn = 8.0;         // mean wind at the camera
		double WindFromDeg = 180.0;  // true direction the wind comes from (north = 0, clockwise)
	};
	/** Rain, or wind over about 20 kn, thins the birds out; soaring needs sun and light wind. 0..1. */
	SAILINGPHYSICS_API double WeatherFactor(EBirdStyle Style, const FWildlifeConditions& C);

	/** What the habitat map asks the world: callbacks so the game passes its terrain and the tools a stand-in. */
	struct FWildlifeWorld
	{
		std::function<double(double North, double East)> HeightAt;   // ground height over the water level (negative = depth)
		std::function<bool(double North, double East)> IsHarbour;    // optional: inside a marina, harbour or dock area
		std::function<double(double North, double East)> CanopyAt;   // optional: tree tops over the ground (m)
	};

	/** A window of habitat cells round a centre, rebuilt as the camera moves (cheap enough for a worker every few km). */
	class SAILINGPHYSICS_API FWildlifeHabitatMap
	{
	public:
		void Build(const FWildlifeWorld& World, double CenterNorth, double CenterEast, double HalfSizeM = 4000.0, double CellM = 50.0);
		bool IsBuilt() const { return Cells > 0; }
		uint32_t BitsAt(double North, double East) const;
		double HeightAt(double North, double East) const;   // the cell's sampled height (negative = depth)
		/** The highest ground or tree top in the cell (a 5 x 5 grid over it, plus half its steepest step), never under the water: what flight clears. */
		double TopAt(double North, double East) const;
		double CenterNorth() const { return CN; }
		double CenterEast() const { return CE; }
		double HalfSize() const { return Half; }
		/** Matching area (km^2) inside a disc round a point. */
		double AreaKm2(uint32_t Bits, double North, double East, double RadiusM) const;
		/** The disc's area (km^2) by habitat pattern: one pass for every bird's area (AreaOf). */
		void Histogram(double North, double East, double RadiusM, std::vector<std::pair<uint32_t, double>>& Out) const;
		static double AreaOf(uint32_t Bits, const std::vector<std::pair<uint32_t, double>>& Histogram);
		/** A random matching cell inside the annulus [MinM, MaxM] round a point; false when none (a few tries). */
		bool Pick(uint32_t Bits, double North, double East, double MinM, double MaxM, FPortableRandom& Rng, double& OutN, double& OutE) const;
		/** A matching cell near a heading from a point (for a flock's next goal), else any matching cell in range. */
		bool PickToward(uint32_t Bits, double North, double East, double HeadingRad, double DistM, FPortableRandom& Rng, double& OutN, double& OutE) const;

	private:
		int Cells = 0;                // cells a side
		double CN = 0.0, CE = 0.0, Half = 0.0, Cell = 50.0;
		std::vector<uint32_t> CellBits;
		std::vector<float> CellHeight;
		std::vector<float> CellTop;
		int Index(double North, double East) const;   // -1 outside
	};

	/** Per tier: how many birds are drawn in each band (the plan's performance table). */
	struct FBirdBudget
	{
		int Far = 300;               // camera-facing quads: 400 m to 2 km, and the nearer birds past the bodies' budget
		int Mid = 60;                // bodies 60 to 400 m: low meshes with wing flaps in the material (and near birds past Near)
		int Near = 12;               // bodies under 60 m: drawn as mid birds until Phase 2's animated near birds
	};
	SAILINGPHYSICS_API FBirdBudget BirdBudgetForTier(int Tier);   // 0 Low .. 3 Ultra

	/** How much bigger than life a bird is drawn, at DistanceM from the camera with PixelAngleRad the angle one screen pixel
	 *  spans (2 tan(fov / 2) / width). A pixel on a 1920-wide screen at 90 degrees spans about 3.6 arcmin of the view where
	 *  the eye resolves about 1, so a gull 500 m off that the eye sees plainly draws under 2 pixels: far birds are drawn up
	 *  to twice their size (as flight sims draw far aircraft), from 1 close by (no change under about 100 m) to 2 past about
	 *  600 m at that screen; a finer screen (more pixels across, a narrower view) needs less, so the distances scale with the
	 *  pixel. A bird's size on screen never shrinks as it comes closer. */
	SAILINGPHYSICS_API double BirdSeenScale(double DistanceM, double PixelAngleRad);

	/** How a bird is coloured when drawn: its back and upper wing, its underside, and how dark its wingtips are (0 none,
	 *  1 black). Linear colour (the renderer's). From field-guide plumage, by species id, else the style's usual look. */
	struct FBirdLook
	{
		float Upper[3] = { 0.4f, 0.42f, 0.45f };
		float Under[3] = { 0.75f, 0.75f, 0.75f };
		float Tips = 0.0f;
	};
	SAILINGPHYSICS_API FBirdLook BirdLookFor(const std::string& Id, EBirdStyle Style, bool* bListed = nullptr);

	enum class EBirdState : unsigned char { Flying, Gliding, Circling, Diving, OnWater, Standing, TakingOff, Landing };

	/** A bird as the renderer draws it. */
	struct FBirdDraw
	{
		double North = 0.0, East = 0.0, Up = 0.0;
		float HeadingRad = 0.0f;     // direction of flight (north = 0, clockwise)
		float PitchRad = 0.0f;       // nose up positive
		float BankRad = 0.0f;        // right wing down positive
		float WingPhase = 0.0f;      // 0..1 through a wingbeat
		float WingAmp = 0.0f;        // 0 wings held (glide), 1 a full beat
		float Fold = 0.0f;           // 0 open, 1 folded (diving, standing, on the water)
		float Fade = 1.0f;           // 0..1 fading in or out at the band's edge
		float SizeM = 1.0f;          // wingspan
		uint16_t Bird = 0;           // index into the table's Birds
		EBirdStyle Style = EBirdStyle::FlapHang;
		EBirdState State = EBirdState::Flying;
		float DistanceM = 0.0f;      // from the camera
		bool bBody = false;          // within the near or mid budget (a body); else a camera-facing quad
		bool bInView = true;         // inside the camera's view cone (always, without a view)
	};

	/** A plunge or a landing on the water, for splashes (Phase 2 draws them). */
	struct FBirdSplash { double North = 0.0, East = 0.0; float SizeM = 1.0f; bool bPlunge = false; };

	/** The camera and the boats that flush the birds. */
	struct FBirdObservers
	{
		double CamNorth = 0.0, CamEast = 0.0, CamUp = 2.0;
		/** The camera's view, optional: birds inside it take the budget first (the rest only rank as if ViewOutsideWeight
		 *  times farther), so the drawn birds are the ones on screen. View is a unit vector (north, east, up); ViewCosHalf the
		 *  cosine of a cone round the screen's corners. */
		bool bHasView = false;
		double ViewNorth = 1.0, ViewEast = 0.0, ViewUp = 0.0, ViewCosHalf = 0.0;
		struct FBoat { double North = 0.0, East = 0.0, HeadingRad = 0.0, SpeedMs = 0.0; bool bPlayer = false; };
		std::vector<FBoat> Boats;
	};

	class SAILINGPHYSICS_API FBirdFlocks
	{
	public:
		static constexpr double FarM = 2000.0;   // the far band's outer edge: flocks live inside it
		static constexpr double MidM = 400.0;    // far band from here out
		static constexpr double NearM = 60.0;    // mid band from here out
		static constexpr double SpawnMinM = 1200.0; // after the first fill new flocks appear only this far out (tiny on screen)
		static constexpr double ViewOutsideWeight = 4.0; // out of view a bird ranks as if this many times farther

		/** Takes the table's birds; Seed makes a run repeatable. */
		void Reset(const FWildlifeTable& Table, uint64_t Seed);
		void SetBudget(const FBirdBudget& B) { Budget = B; }
		/** Density multiplier over every bird (1 = the start values; tuning knob, -SailingWildlifeScale). */
		void SetDensityScale(double S) { DensityScale = S; }

		/** Steps the flocks by Dt seconds of sim time; Map must cover the camera (rebuild it when the camera nears its edge). */
		void Update(double Dt, const FWildlifeConditions& C, const FBirdObservers& Obs, const FWildlifeHabitatMap& Map);

		/** The birds to draw this frame within the budget: in view first, then nearest first. Each near or mid bird within its
		 *  band's budget is a body (bBody); the rest, nearer birds past those budgets included, are quads within Far. */
		const std::vector<FBirdDraw>& Draw() const { return Drawn; }
		/** Splashes since the last Update. */
		const std::vector<FBirdSplash>& Splashes() const { return NewSplashes; }

		/** The flocks a table's bird would have in view now (for the tools and tests). */
		double ExpectedFlocks(int BirdIndex, const FWildlifeConditions& C, const FWildlifeHabitatMap& Map, double North, double East) const;
		/** The same from the area of its habitat inside the far band (km^2). */
		double ExpectedFlocksFor(int BirdIndex, const FWildlifeConditions& C, double AreaKm2) const;
		/** The expected counts the flocks are steered to now (refreshed every few seconds). */
		double ExpectedNow(int BirdIndex) const { return BirdIndex >= 0 && BirdIndex < int(Expected.size()) ? Expected[size_t(BirdIndex)] : 0.0; }

		struct FStats
		{
			int Flocks = 0, Birds = 0, Airborne = 0, Resting = 0, Flushes = 0, Spawned = 0, Retired = 0;
			int Far = 0, Mid = 0, Near = 0;   // drawn: quads, and bodies by the budget they used
			int InView = 0;                   // drawn birds inside the view (all of them without one)
		};
		const FStats& Stats() const { return St; }
		int FlockCountOf(int BirdIndex) const;
		int BirdCountOf(int BirdIndex) const;
		int TableBirds() const { return int(Table.Birds.size()); }
		const FWildBird& TableBird(int I) const { return Table.Birds[size_t(I)]; }

	private:
		struct FMember
		{
			double N = 0.0, E = 0.0, Up = 0.0;
			double Heading = 0.0, Pitch = 0.0, Bank = 0.0;
			double Phase = 0.0;          // wingbeat 0..1
			double CycleT = 0.0;         // where in its flap / glide cycle
			double OffA = 0.0, OffB = 0.0, OffC = 0.0; // slot: loose offsets, circle radius / phase / height
			double TakeOffDelay = 0.0;
			EBirdState State = EBirdState::Flying;
			double StateT = 0.0;
			double DiveFromUp = 0.0;
			double Scale = 1.0;          // this bird's size against the table's wingspan
		};
		struct FPathPoint { double N, E, Up, Heading; };
		struct FFlock
		{
			int Bird = 0;
			uint64_t Seed = 0;
			FPortableRandom Rng;
			double N = 0.0, E = 0.0, Up = 10.0;   // the leader, or the centre of a circling or resting flock
			double Heading = 0.0, Speed = 10.0, TargetUp = 10.0;
			double GoalN = 0.0, GoalE = 0.0;
			double Life = 120.0;                 // seconds until it leaves
			double Age = 0.0;
			double Fade = 0.0;
			bool bCircling = false;
			bool bResting = false;               // on the water or standing on the shore
			bool bFlushed = false;
			bool bLanding = false;
			bool bLeaving = false;
			bool bFollowBoat = false;
			bool bFirstFill = false;             // placed when the camera arrived (not flown in)
			bool bPassing = false;               // on its way past the player's boat (its goal is beside her)
			int Side = 1;                        // echelon side for lines
			std::vector<FMember> Members;
			std::vector<FPathPoint> Path;        // the leader's track, newest last, every PathStep seconds
			double PathT = 0.0;
			double MemberDt = 0.0;               // seconds its birds have not been stepped (an undrawn flock's are every 4th frame)
			bool bDrawn = true;                  // any of its birds drawn last frame
		};

		FWildlifeTable Table;
		FBirdBudget Budget;
		double DensityScale = 1.0;
		uint64_t BaseSeed = 1;
		uint64_t NextFlockId = 1;
		FPortableRandom Rng;
		std::vector<FFlock> Flocks;
		std::vector<FBirdDraw> Drawn;
		std::vector<FBirdSplash> NewSplashes;
		std::vector<double> Expected;     // per table bird, refreshed every few seconds
		std::vector<double> Stay;         // per table bird, the mean seconds a flock of it has counted (births = expected / stay)
		std::vector<double> PathCum;      // StepMembers' scratch: arc length back along a leader's track to each point
		std::vector<std::pair<float, uint32_t>> DrawRank; // BuildDraw's scratch: rank key and index
		std::vector<FBirdDraw> Candidates;            // BuildDraw's scratch: every bird inside the far band
		std::vector<uint32_t> CandidateFlock;         // and its flock
		double ExpectedT = 1e9;
		bool bFilled = false;
		double LastCamN = 0.0, LastCamE = 0.0;
		uint64_t Frame = 0;
		FStats St;

		void RefreshExpected(const FWildlifeConditions& C, const FWildlifeHabitatMap& Map, const FBirdObservers& Obs);
		bool Spawn(int BirdIndex, const FWildlifeConditions& C, const FBirdObservers& Obs, const FWildlifeHabitatMap& Map, double MinM, double MaxM);
		void StepFlock(FFlock& F, double Dt, const FWildlifeConditions& C, const FBirdObservers& Obs, const FWildlifeHabitatMap& Map);
		void StepLeader(FFlock& F, double Dt, const FWildlifeConditions& C, const FBirdObservers& Obs, const FWildlifeHabitatMap& Map);
		void StepMembers(FFlock& F, double Dt, const FWildlifeHabitatMap& Map);
		/** Flushes a resting flock when a boat is inside its flush distance (or always with bForce); true when it lifted. */
		void EndStay(const FFlock& F);
		bool CheckFlush(FFlock& F, const FBirdObservers& Obs, const FWildlifeHabitatMap& Map, bool bForce = false);
		const FBirdObservers::FBoat* PlayerBoat(const FBirdObservers& Obs) const;
		/** Where a flock of this bird may sit (the cells it rests in: water, or shallow water for waders). */
		bool CanRestAt(const FWildBird& B, const FWildlifeHabitatMap& Map, double North, double East) const;
		void NewGoal(FFlock& F, const FWildlifeHabitatMap& Map, double DistM);
		void BuildDraw(const FBirdObservers& Obs);
		int GroupSize(const FWildBird& B, FPortableRandom& R) const;
	};
}
