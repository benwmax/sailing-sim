#pragma once

#include "CoreMinimal.h"
#include "Sail.h"

/**
 * Visual V3: the sails as cloth.
 *
 * Shape. Each frame the sail's target shape comes from the physics strips (Sail.h): the chord angle (twist), camber and
 * flow of every strip, interpolated over a finer grid (rows up the luff, columns along the chord), with the planform
 * from the sail's geometry: luff line, chords, a headboard on the main, the roach. The rendered sail is the one the
 * forces came from (SailingSim.Visual.SailShape).
 *
 * Cloth. On Medium and High a light position-based cloth layer follows that target: stiffly where the sail is drawing,
 * loosely where it luffs, so an eased sail flogs and a blown spinnaker collapses and refills; the leech flutters at
 * speed and the luff wrinkles when the halyard (Cunningham) is soft in a breeze. The luff, and the boom foot of the
 * main, are held to the spars; the jib clew to its sheet. Low draws the target shape directly, as before.
 *
 * Marks. UV0 is metres (along the chord from the luff, up from the foot), UV1 the normalized planform (0..1 both
 * ways), UV2.x metres from the leech: the cloth material (M_SailCloth) draws the seams, batten pockets, class insignia
 * and sail number from them.
 *
 * Telltales. Pure rules, shared by the ribbons and SailingSim.Visual.Telltales: a jib telltale lifts on the windward
 * side when you pinch (the luff angle), stalls on the leeward side when over-sheeted; a leech telltale streams while
 * the flow leaves the leech cleanly and curls behind it when the main stalls.
 */
enum class ETelltaleState : uint8 { Streaming, Lifting, Stalled, Fluttering };

SAILINGSIM_API ETelltaleState JibTelltaleState(const Sailing::FSailStripState& Strip, bool bWindwardFace);
SAILINGSIM_API ETelltaleState LeechTelltaleState(const Sailing::FSailStripState& Strip);

enum class ESailKind : uint8 { Main, Jib, Spinnaker };

struct FSailClothDrive
{
	float DeltaSeconds = 1.f / 60.f;
	float Time = 0.f;
	float ApparentWindKnots = 10.f;
	float Cunningham = 0.f;         // 0 = halyard soft (luff wrinkles in a breeze), 1 = tight
	FVector GravityBody = FVector(0.0, 0.0, -1.0); // gravity in the boat frame (she heels)
	bool bSimulate = true;          // false: draw the target shape (Low tier)
};

/** Rig clearance: a wire the sail can't pass through (boat frame, cm): a shroud, a spreader, a trapeze wire. */
struct FSailObstacle
{
	FVector A, B;
	float RadiusCm = 1.f;
	// How much of each end the sail leaves to the spars and the deck (a wire's tang at the mast, its chainplate); 0 where a
	// wire drawn in pieces carries on.
	float FreeA = 12.f, FreeB = 12.f;
};

class SAILINGSIM_API FSailCloth
{
public:
	static constexpr int32 Rows = 25;
	static constexpr int32 Cols = 16;
	/** A vertex further than this from its target means the cloth ran away; Step starts it again from the target. */
	static constexpr float kRunawayCm = 600.f;

	/** Sets up the planform for a sail (rebuilt when the boat changes or the main is reefed). */
	void Init(const Sailing::FSailGeometry& Geo, ESailKind Kind);

	/** Forgets the cloth's motion: the next Step starts again from the target shape (the boat was reset or moved). */
	void Reset() { bStarted = false; Accumulator = 0.f; }

	/** The target shape (boat frame, cm) for the strips' current state; Side = +1 sail to starboard, -1 to port. */
	void ComputeTarget(const Sailing::FSailStripState* Strips, int32 Side, TArray<FVector>& Out) const;

	/** The wires this sail keeps clear of from the next Step (the pawn's shrouds and spreaders). */
	void SetObstacles(const TArray<FSailObstacle>& In) { Obstacles = In; }
	/** How far the main's foot was turned to keep clear (radians about the boat's Z, + = from X toward Y): the boom is
	 *  drawn turned with it (stopped at the shroud). */
	float GetFootTurn() const { return FootTurn; }
	/** Advances the cloth toward the target shape (or snaps to it when not simulating). */
	void Step(const Sailing::FSailStripState* Strips, int32 Side, const FSailClothDrive& Drive);

	const TArray<FVector>& Positions() const { return Pos; }
	const TArray<FVector2D>& UV0() const { return UVMeters; }
	const TArray<FVector2D>& UV1() const { return UVNormal; }
	const TArray<FVector2D>& UV2() const { return UVLeech; }
	void ComputeNormals(TArray<FVector>& Out) const { NormalsOf(Pos, Out); }
	/** The grid normals of any positions laid out as the cloth's (the target's, for the luff wrinkles). */
	static void NormalsOf(const TArray<FVector>& P, TArray<FVector>& Out);
	/** Graphics G6: tangents along the chord (UV0.x), for M_SailCloth's creases (a tangent-space normal). */
	void ComputeTangents(TArray<struct FProcMeshTangent>& Out) const;
	void Triangles(TArray<int32>& Out) const;

	/** A point on the sail at normalized chord u and height v (bilinear on the current cloth), and the sail's normal
	 *  there (toward the leeward side for Side = +1 ... the side the sail bellies to). */
	FVector PointAt(float U, float V) const;
	FVector NormalAt(float U, float V) const;
	FVector ChordTangentAt(float U, float V) const;

	ESailKind GetKind() const { return Kind; }
	bool IsValid() const { return NumStrips > 0; }
	/** Mean tension (0 = slack, 1 = drawing) of the rows, for the sheets' sag. */
	float Load() const { return MeanLoad; }

private:
	struct FRowShape { double Z, LuffX, Chord, Angle, Camber, Load; };
	void RowAt(const Sailing::FSailStripState* Strips, int32 Side, int32 R, FRowShape& Out) const;
	static int32 Index(int32 R, int32 C) { return R * Cols + C; }
	/** Rig clearance: puts the cloth back on the clew's side of every obstacle it passed through (the main eased onto the
	 *  shrouds and spreaders, a genoa sheeted onto them), as the cloth presses on a wire instead of passing it. */
	void KeepClear(TArray<FVector>& P, bool bTarget = false);
	TArray<FSailObstacle> Obstacles;
	float FootTurn = 0.f;
	float MainTurn = 0.f;  // the main's turn off the wires, eased (KeepClear)
	float TurnDt = 0.f;

	Sailing::FSailGeometry Geo;
	ESailKind Kind = ESailKind::Main;
	int32 NumStrips = 0;
	double ZFoot = 0.0, ZHead = 1.0, LuffSlope = 0.0, LuffZ0 = 0.0;
	TArray<double> RowChord;   // planform chord per row (m)
	TArray<FVector> Pos, Prev, Target;
	TArray<FVector2D> UVMeters, UVNormal, UVLeech;
	TArray<float> RowLoad;     // each row's tension as the cloth feels it (eased toward its strip's: RowAt)
	float MeanLoad = 1.f;
	bool bStarted = false;
	float Accumulator = 0.f;
};
