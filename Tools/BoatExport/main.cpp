// Visual phases: writes a boat's physics geometry as JSON for the Blender model scripts (Tools/blender), so the visual
// model is built from the same numbers the physics floats and sails (the physics config is the source of truth).
// Build and run with scripts/make-boat-models.sh. Usage: boat-export <j22|...> <out.json>
#include "BoatModel.h"
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>

using namespace Sailing;

namespace
{
	std::string V3(const Vec3& V)
	{
		char B[96];
		std::snprintf(B, sizeof(B), "[%.5f, %.5f, %.5f]", V.X, V.Y, V.Z);
		return B;
	}

	std::string Sail(const FSailGeometry& S)
	{
		std::string Out = "[";
		for (int I = 0; I < S.NumStrips; ++I)
		{
			const FSailStripGeometry& T = S.Strips[I];
			char B[160];
			std::snprintf(B, sizeof(B), "%s{\"z_bottom\": %.4f, \"z_top\": %.4f, \"luff_x\": %.4f, \"chord\": %.4f}", I ? ", " : "", T.ZBottom, T.ZTop, T.LuffX, T.Chord);
			Out += B;
		}
		return Out + "]";
	}
}

int main(int Argc, char** Argv)
{
	if (Argc < 3)
	{
		std::fprintf(stderr, "usage: boat-export <j22|sunfish|ilca7|catalina22|catalina30|hobie16|corsair880|lagoon42> <out.json>\n");
		return 2;
	}
	static const char* Names[] = { "j22", "sunfish", "ilca7", "catalina22", "catalina30", "hobie16", "corsair880", "lagoon42" };
	int TypeIndex = -1;
	for (int I = 0; I < int(sizeof(Names) / sizeof(Names[0])); ++I) if (std::strcmp(Argv[1], Names[I]) == 0) TypeIndex = I;
	if (TypeIndex < 0) { std::fprintf(stderr, "unknown boat %s\n", Argv[1]); return 2; }
	const FBoatConfig C = FBoatConfig::Make(EBoatType(TypeIndex));
	const FBoatModel Boat(C);
	const FHullShape& H = C.Hulls[0];
	const Vec3 CB = Boat.DesignBuoyancyCentre();

	FILE* F = std::fopen(Argv[2], "w");
	if (!F) return 1;
	std::fprintf(F, "{\n  \"name\": \"%s\",\n", C.Name);
	std::fprintf(F, "  \"loa\": %.4f, \"beam\": %.4f, \"draft\": %.4f, \"lwl\": %.4f,\n", C.LengthOverall, C.Beam, C.Draft, C.WaterlineLength);
	std::fprintf(F, "  \"canoe_depth\": %.5f, \"design_volume\": %.5f, \"design_cb\": %s,\n", Boat.HullDepth(), Boat.DesignDisplacedVolume(), V3(CB).c_str());
	std::fprintf(F, "  \"hull\": {\"bow_x\": %.4f, \"stern_x\": %.4f, \"waterline_mid_x\": %.4f, \"waterline_half_length\": %.4f, "
		"\"max_half_beam\": %.4f, \"max_beam_x\": %.4f, \"aft_length\": %.4f, \"transom_beam_loss\": %.4f, \"sheer_z\": %.4f, "
		"\"sheer_rise\": %.4f, \"sheer_rise_from_x\": %.4f, \"bow_overhang_slope\": %.4f, \"stern_overhang_slope\": %.4f, \"bilge_power\": %.4f},\n",
		H.BowX, H.SternX, H.WaterlineMidX, H.WaterlineHalfLength, H.MaxHalfBeam, H.MaxBeamX, H.AftLength, H.TransomBeamLoss,
		H.SheerZ, H.SheerRise, H.SheerRiseFromX, H.BowOverhangSlope, H.SternOverhangSlope, H.BilgePower);
	// Every hull (Visual V7: the cats and the trimaran), the same fields plus its lateral place and depth.
	std::fprintf(F, "  \"multihull\": %s, \"hulls\": [", C.bMultihull ? "true" : "false");
	for (size_t I = 0; I < C.Hulls.size(); ++I)
	{
		const FHullShape& K = C.Hulls[I];
		std::fprintf(F, "%s{\"center_y\": %.4f, \"bow_x\": %.4f, \"stern_x\": %.4f, \"waterline_mid_x\": %.4f, \"waterline_half_length\": %.4f, "
			"\"max_half_beam\": %.4f, \"max_beam_x\": %.4f, \"aft_length\": %.4f, \"transom_beam_loss\": %.4f, \"sheer_z\": %.4f, "
			"\"sheer_rise\": %.4f, \"sheer_rise_from_x\": %.4f, \"bow_overhang_slope\": %.4f, \"stern_overhang_slope\": %.4f, \"bilge_power\": %.4f, "
			"\"depth_scale\": %.4f, \"depth_offset\": %.4f}", I ? ", " : "", K.CenterY, K.BowX, K.SternX, K.WaterlineMidX, K.WaterlineHalfLength, K.MaxHalfBeam,
			K.MaxBeamX, K.AftLength, K.TransomBeamLoss, K.SheerZ, K.SheerRise, K.SheerRiseFromX, K.BowOverhangSlope, K.SternOverhangSlope, K.BilgePower,
			K.DepthScale, K.DepthOffset);
	}
	std::fprintf(F, "],\n");
	std::fprintf(F, "  \"engines\": [");
	for (size_t I = 0; I < C.Engines.size(); ++I) std::fprintf(F, "%s{\"position\": %s, \"hull\": %d}", I ? ", " : "", V3(C.Engines[I].Position).c_str(), C.Engines[I].Hull);
	std::fprintf(F, "],\n");
	std::fprintf(F, "  \"foils\": [");
	for (size_t I = 0; I < C.Foils.size(); ++I)
	{
		const FFoilDef& D = C.Foils[I];
		const char* Role = D.Role == EFoilRole::Keel ? "keel" : (D.Role == EFoilRole::Rudder ? "rudder" : (D.Role == EFoilRole::Board ? "board" : "hull"));
		std::fprintf(F, "%s{\"role\": \"%s\", \"center\": %s, \"area\": %.4f, \"chord\": %.4f, \"span\": %.4f, \"hull\": %d, \"retractable\": %s}", I ? ", " : "", Role,
			V3(D.Params.Center).c_str(), D.Params.Area, D.Params.Chord, D.Span(), D.Hull, D.bRetractable ? "true" : "false");
	}
	std::fprintf(F, "],\n");
	std::fprintf(F, "  \"rig\": {\"mast_x\": %.4f, \"masthead_z\": %.4f, \"mast_diameter\": %.4f, \"boom_z\": %.4f, \"main_luff_x\": %.4f, "
		"\"main_foot_chord\": %.4f, \"tiller_length\": %.4f},\n", C.MastX, C.MastheadZ, C.MastDiameter, C.BoomZ, C.MainLuffX, C.MainFootChord, C.TillerLength);
	std::fprintf(F, "  \"main\": %s,\n  \"jib\": %s,\n  \"spinnaker\": %s,\n", Sail(C.Main).c_str(), Sail(C.Jib).c_str(), Sail(C.Spinnaker).c_str());
	std::fprintf(F, "  \"asymmetric_spinnaker\": %s, \"spar_float\": %.2f,\n", C.bAsymmetricSpinnaker ? "true" : "false", C.SparFloatLiters);
	std::fprintf(F, "  \"crew\": {\"count\": %d, \"cg\": %s}\n}\n", C.CrewCount, V3(C.CrewCG).c_str());
	std::fclose(F);
	std::printf("%s: canoe depth %.3f m, displaced %.3f m^3, centre of buoyancy (%.3f, %.3f, %.3f)\n", C.Name, Boat.HullDepth(), Boat.DesignDisplacedVolume(), CB.X, CB.Y, CB.Z);
	return 0;
}
