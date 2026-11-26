#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ShipWalk.h"

#include <algorithm>
#include <deque>
#include <limits>
#include <string>
#include <vector>

#if WITH_DEV_AUTOMATION_TESTS

/**
 * Walking a ship (docs/ship-walk/): the walker in the ship's frame on a baked walk map. A made-up two-deck ship here (a spar
 * deck with a hatch over a gun deck with beams every 0.8 m and a mast), then the frigate's and Bluebonnet's own maps when they are in the tree.
 */
namespace
{
	constexpr EAutomationTestFlags ShipWalkFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
	constexpr double kFrame = 1.0 / 60.0;
	const Sailing::Vec3 kUpright(0.0, 0.0, -Sailing::kGravity);

	/** Felt gravity on a deck heeled HeelDeg with the starboard side down (pulls toward +Y). */
	Sailing::Vec3 Heeled(double HeelDeg)
	{
		const double H = HeelDeg * Sailing::kDegToRad;
		return { 0.0, Sailing::kGravity * FMath::Sin(H), -Sailing::kGravity * FMath::Cos(H) };
	}

	Sailing::FWalkDeck MakeDeck(const char* Name, double Z, bool bGunDeck)
	{
		Sailing::FWalkDeck D;
		D.Name = Name;
		D.Cell = 0.1;
		D.X0 = -10.0;
		D.Y0 = -3.0;
		D.NX = 201;
		D.NY = 61;
		D.Floor.assign(size_t(D.NX) * D.NY, float(Z));
		D.Overhead.assign(size_t(D.NX) * D.NY, bGunDeck ? 3.96f : std::numeric_limits<float>::infinity());
		for (int J = 0; J < D.NY; ++J)
		{
			for (int I = 0; I < D.NX; ++I)
			{
				const double X = D.X0 + I * D.Cell, Y = D.Y0 + J * D.Cell;
				const int K = D.Index(I, J);
				D.Floor[K] = float(Z + 0.05 * (1.0 - (Y / 3.0) * (Y / 3.0)));   // 5 cm of camber
				if (bGunDeck && FMath::Fmod(X + 100.0, 0.8) < 0.2) D.Overhead[K] = 3.72f;   // a beam, 1.67 m over the planks
				const bool bHatch = X >= -0.05 && X <= 1.55 && FMath::Abs(Y) <= 0.75;
				if (!bGunDeck && bHatch) D.Floor[K] = std::numeric_limits<float>::quiet_NaN();   // the hatch
				if (bGunDeck && bHatch) D.Overhead[K] = std::numeric_limits<float>::infinity();    // open up through it
				if (bGunDeck && FMath::Abs(X - 5.0) < 0.3 && FMath::Abs(Y) < 0.3) D.Floor[K] = std::numeric_limits<float>::quiet_NaN();     // a mast
			}
		}
		return D;
	}

	Sailing::FWalkMap MakeShip()
	{
		Sailing::FWalkMap M;
		M.Decks.push_back(MakeDeck("Spar", 4.0, false));
		M.Decks.push_back(MakeDeck("Gun", 2.0, true));
		M.Decks[0].AlsoLoad = 1u << 1;   // the gun deck shows through the hatch
		Sailing::FWalkLink L;
		L.Lower = 1;
		L.Upper = 0;
		L.Foot = Sailing::Vec3(2.0, 0.0, 2.05);
		L.Top = Sailing::Vec3(-0.4, 0.0, 4.05);
		L.Name = "AfterHatch";
		M.Links.push_back(L);
		Sailing::FWalkSpot Helm;
		Helm.Name = "Helm";
		Helm.Deck = 0;
		Helm.X = -6.0;
		M.Spots.push_back(Helm);
		M.Finish();
		return M;
	}

	/** The made-up ship as the game reads it: written and parsed again. */
	bool LoadShip(FAutomationTestBase& Test, Sailing::FWalkMap& Out)
	{
		const std::vector<uint8_t> Bytes = MakeShip().Write();
		std::string Error;
		const bool bOk = Out.Parse(Bytes.data(), Bytes.size(), &Error);
		Test.TestTrue(FString::Printf(TEXT("the walk file parses (%hs)"), Error.c_str()), bOk);
		return bOk;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipWalkHelmStandTest, "SailingSim.ShipWalk.HelmStand", ShipWalkFlags)
bool FShipWalkHelmStandTest::RunTest(const FString& Parameters)
{
	using Sailing::FWalkMap;
	// Commonwealth's first bake: the spot 0.7 m abaft the axle at -22.25 stands back to 1.05 m abaft it.
	TestEqual(TEXT("a spot inside the wheel stands back"), FWalkMap::HelmStandX(-22.95, -22.25), -22.25 - FWalkMap::HelmAbaftWheelAxle);
	// A spot already clear of the wheel, or a tiller boat's spot forward of a wheel frame it does not have, is kept.
	TestEqual(TEXT("a spot clear of the wheel is kept"), FWalkMap::HelmStandX(-24.2, -22.25), -24.2);
	TestEqual(TEXT("the standoff is a stride past the after wheel, not a cabin"), FWalkMap::HelmAbaftWheelAxle > 1.4 && FWalkMap::HelmAbaftWheelAxle < 2.0, true);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipWalkFileTest, "SailingSim.ShipWalk.File", ShipWalkFlags)
bool FShipWalkFileTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	const FWalkMap Made = MakeShip();
	const std::vector<uint8_t> Bytes = Made.Write();
	FWalkMap M;
	if (!LoadShip(*this, M)) return false;
	TestTrue(TEXT("two decks and a ladder"), M.Decks.size() == 2 && M.Links.size() == 1);
	TestTrue(TEXT("floors to the millimetre"), FMath::Abs(M.Decks[0].FloorAt(3.0, 0.4) - Made.Decks[0].FloorAt(3.0, 0.4)) < 0.002);
	TestTrue(TEXT("beams to the millimetre"), FMath::Abs(M.Decks[1].OverheadAt(2.45, 0.0) - 3.72) < 0.002);
	TestTrue(TEXT("open sky stays open"), !std::isfinite(M.Decks[0].OverheadAt(3.0, 0.0)));
	TestTrue(TEXT("no floor in the hatch"), !std::isfinite(M.Decks[0].FloorAt(0.7, 0.0)));
	TestTrue(TEXT("the ladder's name"), M.Links[0].Name == "AfterHatch");
	const FWalkSpot* Helm = M.SpotNamed("Helm");
	TestTrue(TEXT("the helm spot"), Helm && Helm->Deck == 0 && Helm->X == -6.0 && Helm->YawDeg == 0.0);
	TestTrue(TEXT("no spot by another name"), M.SpotNamed("Galley") == nullptr);
	// A version 1 file (before the spots) still reads, with none: the same bytes less the spots, version 1.
	{
		const size_t SpotBytes = 4 + 1 + 1 + 4 + 4 * 8;
		std::vector<uint8_t> V1(Bytes.begin(), Bytes.end() - std::ptrdiff_t(SpotBytes));
		V1[4] = 1;
		FWalkMap Old;
		std::string OldError;
		TestTrue(FString::Printf(TEXT("a version 1 file reads (%hs)"), OldError.c_str()), Old.Parse(V1.data(), V1.size(), &OldError) && Old.Spots.empty() && Old.Links.size() == 1);
	}
	// A version 2 file (spots without their height) still reads, each spot at height 0.
	{
		std::vector<uint8_t> V2(Bytes.begin(), Bytes.end() - 8);
		V2[4] = 2;
		FWalkMap Old;
		std::string OldError;
		TestTrue(FString::Printf(TEXT("a version 2 file reads (%hs)"), OldError.c_str()),
			Old.Parse(V2.data(), V2.size(), &OldError) && Old.Spots.size() == 1 && Old.Spots[0].X == -6.0 && Old.Spots[0].Z == 0.0);
	}
	// Where a body fits: clear of the hatch's edge and the ship's side by its radius.
	TestFalse(TEXT("no standing at the hatch's lip"), M.Decks[0].CanStand(-0.1, 0.0));
	TestTrue(TEXT("standing at the ladder's top"), M.Decks[0].CanStand(-0.4, 0.0));
	TestFalse(TEXT("no standing against the side"), M.Decks[0].CanStand(3.0, 2.95));
	TestFalse(TEXT("no standing in the mast"), M.Decks[1].CanStand(5.0, 0.0));
	// Anything malformed is refused whole.
	std::string Error;
	FWalkMap Bad;
	TestFalse(TEXT("a cut-short file is refused"), Bad.Parse(Bytes.data(), Bytes.size() - 3, &Error));
	TestFalse(TEXT("and leaves the map empty"), Bad.IsLoaded());
	std::vector<uint8_t> Wrong = Bytes;
	Wrong[0] ^= 0xFF;
	TestFalse(TEXT("a wrong magic is refused"), Bad.Parse(Wrong.data(), Wrong.size(), &Error));
	std::vector<uint8_t> Longer = Bytes;
	Longer.push_back(0);
	TestFalse(TEXT("trailing bytes are refused"), Bad.Parse(Longer.data(), Longer.size(), &Error));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipWalkLadderTest, "SailingSim.ShipWalk.Ladders", ShipWalkFlags)
bool FShipWalkLadderTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	FWalkMap M;
	if (!LoadShip(*this, M)) return false;
	FShipWalker W;
	FWalkInput In;
	In.Forward = 1.0;
	// From forward of the hatch, facing aft: the hatch's forward coaming stops him (no ladder that side).
	TestTrue(TEXT("reset on the spar deck"), W.Reset(M, 0, 5.0, 0.0, 180.0));
	for (int S = 0; S < 300; ++S) W.Step(M, In, kUpright, kFrame);
	TestTrue(TEXT("stopped at the hatch, still on deck"), W.GetDeck() == 0 && W.GetLink() < 0 && W.GetFeet().X > 1.7);
	// From aft of it, walking forward: onto the ladder's top.
	W.Reset(M, 0, -2.0, 0.0, 0.0);
	for (int S = 0; S < 120 && W.GetLink() < 0; ++S) W.Step(M, In, kUpright, kFrame);
	TestTrue(TEXT("on the ladder at its top"), W.GetLink() == 0 && W.GetLinkT() == 1.0);
	TestTrue(TEXT("both decks wanted on the ladder"), W.DecksWanted(M) == 3u);
	// Down it, still holding forward (forward carries on the way he got on), and off at its foot.
	int S = 0;
	for (; S < 1200 && W.GetLink() >= 0; ++S) W.Step(M, In, kUpright, kFrame);
	const double Seconds = S * kFrame;
	TestTrue(FString::Printf(TEXT("down in %.1f s (a 3.1 m ladder at 0.8 m/s)"), Seconds), Seconds > 3.0 && Seconds < 5.0);
	TestTrue(TEXT("on the gun deck at the foot"), W.GetDeck() == 1 && FMath::Abs(W.GetFeet().Z - 2.05) < 0.06);
	// Backing toward the ladder, facing away from it, doesn't put him straight back on it.
	In.Forward = -1.0;
	for (int K = 0; K < 60; ++K) W.Step(M, In, kUpright, kFrame);
	TestTrue(TEXT("backing away stays on the deck"), W.GetLink() < 0 && W.GetDeck() == 1);
	// Use takes it from the foot whichever way he faces.
	W.Reset(M, 1, 2.2, 0.2, 90.0);
	In = FWalkInput();
	In.bUse = true;
	W.Step(M, In, kUpright, kFrame);
	TestTrue(TEXT("Use takes the ladder"), W.GetLink() == 0 && W.GetLinkT() == 0.0);
	In = FWalkInput();
	In.Forward = 1.0;
	for (int K = 0; K < 1200 && W.GetLink() >= 0; ++K) W.Step(M, In, kUpright, kFrame);
	TestTrue(TEXT("up and off on the spar deck"), W.GetDeck() == 0 && W.GetLink() < 0);
	// Away from the ladder only his deck (and what it names) is wanted.
	W.Reset(M, 1, 8.5, 0.0, 0.0);
	TestTrue(TEXT("far from the ladder: the gun deck alone"), W.DecksWanted(M) == 2u);
	TestTrue(TEXT("the spar deck is his overhead there (shown, unlit)"), W.DecksOverhead(M) == 1u);
	W.Reset(M, 0, 8.0, 0.0, 0.0);
	TestTrue(TEXT("the spar deck keeps the gun deck (AlsoLoad)"), W.DecksWanted(M) == 3u);
	TestTrue(TEXT("from the spar deck, the gun deck it keeps lies under the spar deck itself"), W.DecksOverhead(M) == 1u);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipWalkBeamsTest, "SailingSim.ShipWalk.Beams", ShipWalkFlags)
bool FShipWalkBeamsTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	FWalkMap M;
	if (!LoadShip(*this, M)) return false;
	FShipWalker W;
	FWalkInput In;
	In.Forward = 1.0;
	W.Reset(M, 1, -8.0, 1.0, 0.0);
	double LeastRoom = 1e9;
	int Ducking = 0;
	for (int S = 0; S < 600; ++S)
	{
		W.Step(M, In, kUpright, kFrame);
		const Vec3 E = W.GetEye();
		LeastRoom = FMath::Min(LeastRoom, M.Decks[1].OverheadAt(E.X, E.Y) - E.Z);
		Ducking += W.IsDucking() ? 1 : 0;
	}
	TestTrue(FString::Printf(TEXT("the eye keeps under the beams (least room %.3f m)"), LeastRoom), LeastRoom >= FShipWalker::HeadOverEye - 1e-6);
	TestTrue(TEXT("he ducks under them"), Ducking > 0);
	TestTrue(FString::Printf(TEXT("and still makes way (x %.1f)"), W.GetFeet().X), W.GetFeet().X > -3.0);
	// The mast stops him a body's radius off.
	W.Reset(M, 1, 3.0, 0.0, 0.0);
	for (int S = 0; S < 300; ++S) W.Step(M, In, kUpright, kFrame);
	TestTrue(FString::Printf(TEXT("stopped by the mast (x %.2f)"), W.GetFeet().X), W.GetFeet().X < 5.0 - 0.3 - FWalkMap::BodyRadius + 0.11);
	// In the open his eye is a standing man's, and a crouch drops it.
	W.Reset(M, 0, 8.0, 0.0, 0.0);
	In = FWalkInput();
	for (int S = 0; S < 60; ++S) W.Step(M, In, kUpright, kFrame);
	TestTrue(TEXT("standing eye in the open"), FMath::Abs(W.GetEyeHeight() - FShipWalker::EyeStand) < 0.01);
	In.bCrouch = true;
	for (int S = 0; S < 60; ++S) W.Step(M, In, kUpright, kFrame);
	TestTrue(TEXT("crouching eye"), FMath::Abs(W.GetEyeHeight() - FShipWalker::EyeCrouch) < 0.01);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipWalkHeelTest, "SailingSim.ShipWalk.Heel", ShipWalkFlags)
bool FShipWalkHeelTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	FWalkMap M;
	if (!LoadShip(*this, M)) return false;
	FShipWalker W;
	FWalkInput In;
	In.Forward = 1.0;
	// 15 deg of heel: across the deck, downhill is quicker than uphill and his feet hold.
	W.Reset(M, 0, 8.0, -2.0, 90.0);
	for (int S = 0; S < 30; ++S) W.Step(M, In, Heeled(15.0), kFrame);
	const double Down = W.GetVelocity().Y;
	W.Reset(M, 0, 8.0, 2.0, -90.0);
	for (int S = 0; S < 30; ++S) W.Step(M, In, Heeled(15.0), kFrame);
	const double Up = -W.GetVelocity().Y;
	TestTrue(FString::Printf(TEXT("downhill %.2f m/s, uphill %.2f m/s"), Down, Up), Down > Up * 1.3 && Up > 0.5);
	TestFalse(TEXT("no slide at 15 deg"), W.IsSliding());
	// 30 deg: he slides to leeward with no input, and fetches up against the side still on the deck.
	W.Reset(M, 0, 8.0, -2.0, 0.0);
	In = FWalkInput();
	for (int S = 0; S < 60; ++S) W.Step(M, In, Heeled(30.0), kFrame);
	TestTrue(FString::Printf(TEXT("slides at 30 deg (y %.2f)"), W.GetFeet().Y), W.IsSliding() && W.GetFeet().Y > -1.9);
	for (int S = 0; S < 600; ++S) W.Step(M, In, Heeled(30.0), kFrame);
	TestTrue(TEXT("stopped by the side, on the deck"), M.Decks[0].CanStand(W.GetFeet().X, W.GetFeet().Y) && W.GetFeet().Y > 2.0);
	// Upright again, his feet catch.
	for (int S = 0; S < 120; ++S) W.Step(M, In, kUpright, kFrame);
	TestTrue(TEXT("stops once the deck comes back"), W.GetVelocity().LengthXY() < 0.01);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipWalkWanderTest, "SailingSim.ShipWalk.Wander", ShipWalkFlags)
bool FShipWalkWanderTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	FWalkMap M;
	if (!LoadShip(*this, M)) return false;
	// Ten minutes of a random walker rolling 20 deg each way: never off a floor he fits on, never inside a beam.
	FShipWalker W;
	W.Reset(M, 1, 2.0, 0.5, 0.0);
	uint32 Seed = 1;
	auto Rand = [&Seed]() { Seed = Seed * 1103515245u + 12345u; return double((Seed >> 8) & 0xFFFF) / 32767.5 - 1.0; };
	FWalkInput In;
	int Off = 0, InBeam = 0, Climbs = 0;
	int Frames[2] = { 0, 0 };
	for (int S = 0; S < 60 * 600; ++S)
	{
		if (S % 30 == 0) { In.Forward = Rand(); In.Right = Rand(); In.bRun = Rand() > 0.5; In.bCrouch = Rand() > 0.8; }
		In.LookYawDeg = Rand() * 3.0;
		In.bUse = Rand() > 0.9;
		// Every other ten seconds he makes for the ladder and takes it, up or down by the half minute.
		if ((S / 600) % 2 == 1)
		{
			if (W.GetLink() < 0)
			{
				const FWalkLink& L = M.Links[0];
				const Vec3 End = L.Lower == W.GetDeck() ? L.Foot : L.Top;
				const double Want = FMath::RadiansToDegrees(FMath::Atan2(End.Y - W.GetFeet().Y, End.X - W.GetFeet().X));
				In.LookYawDeg = FMath::Clamp(FMath::FindDeltaAngleDegrees(W.GetYawDeg(), Want), -6.0, 6.0);
				In.Forward = 1.0;
				In.Right = 0.0;
				In.bUse = true;
			}
			else
			{
				In.Forward = (S / 1200) % 2 ? 1.0 : -1.0;
			}
		}
		const int WasLink = W.GetLink();
		W.Step(M, In, Heeled(20.0 * FMath::Sin(S * kFrame * 2.0 * PI / 9.0)), kFrame);
		if (W.GetLink() >= 0 && WasLink < 0) ++Climbs;
		if (W.GetLink() >= 0)
		{
			// On the ladder: his eye under whatever is over his feet on either deck.
			const FWalkLink& L = M.Links[W.GetLink()];
			const Vec3 F = W.GetFeet(), E = W.GetEye();
			for (int K : { L.Lower, L.Upper })
			{
				const double Over = M.Decks[K].OverheadAt(F.X, F.Y);
				if (std::isfinite(Over) && Over > F.Z + FShipWalker::LadderKnee && Over - E.Z < FShipWalker::HeadOverEye - 1e-6) { ++InBeam; break; }
			}
			continue;
		}
		const FWalkDeck& D = M.Decks[W.GetDeck()];
		++Frames[W.GetDeck()];
		if (!D.CanStand(W.GetFeet().X, W.GetFeet().Y)) ++Off;
		const Vec3 E = W.GetEye();
		if (D.OverheadAt(E.X, E.Y) - E.Z < FShipWalker::HeadOverEye - 1e-6) ++InBeam;
	}
	AddInfo(FString::Printf(TEXT("frames on the spar deck %d, gun deck %d; ladders taken %d"), Frames[0], Frames[1], Climbs));
	TestEqual(TEXT("frames off the floor"), Off, 0);
	TestEqual(TEXT("frames with the eye in a beam"), InBeam, 0);
	TestTrue(TEXT("he found the ladder"), Climbs > 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipWalkCommonwealthTest, "SailingSim.ShipWalk.Commonwealth", ShipWalkFlags)
bool FShipWalkCommonwealthTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	// The frigate's own map (Tools/shipkit/frigate/walk.py): each ladder's ends are somewhere to stand, every deck is reached
	// from the spar deck, and the walk from the wheel down to the lowest deck works.
	const FString Path = FPaths::ProjectContentDir() / TEXT("TerrainData/Ships/Commonwealth.walk");
	TArray<uint8> Bytes;
	if (!FFileHelper::LoadFileToArray(Bytes, *Path, FILEREAD_Silent))
	{
		AddInfo(TEXT("no Commonwealth.walk in the tree yet: skipped"));
		return true;
	}
	FWalkMap M;
	std::string Error;
	if (!TestTrue(TEXT("Commonwealth.walk parses"), M.Parse(Bytes.GetData(), size_t(Bytes.Num()), &Error))) return false;
	const int Spar = M.DeckNamed("Spar");
	TestTrue(TEXT("a spar deck"), Spar >= 0);
	for (const FWalkLink& L : M.Links)
	{
		const FString Name = UTF8_TO_TCHAR(L.Name.c_str());
		TestTrue(FString::Printf(TEXT("%s: its foot is somewhere to stand"), *Name), M.Decks[L.Lower].CanStand(L.Foot.X, L.Foot.Y));
		TestTrue(FString::Printf(TEXT("%s: its top is somewhere to stand"), *Name), M.Decks[L.Upper].CanStand(L.Top.X, L.Top.Y));
		TestTrue(FString::Printf(TEXT("%s: the top is over the foot"), *Name), L.Top.Z > L.Foot.Z + 0.5);
	}
	uint32 Reached = Spar >= 0 ? (1u << Spar) : 0u;
	for (size_t Pass = 0; Pass < M.Decks.size(); ++Pass)
	{
		for (const FWalkLink& L : M.Links)
		{
			if (Reached & ((1u << L.Lower) | (1u << L.Upper))) Reached |= (1u << L.Lower) | (1u << L.Upper);
		}
	}
	for (size_t D = 0; D < M.Decks.size(); ++D)
	{
		TestTrue(FString::Printf(TEXT("deck %hs is reached by ladder"), M.Decks[D].Name.c_str()), (Reached & (1u << D)) != 0);
	}
	return true;
}

namespace
{
	/** Cell centres of a shortest standing path on D from (X0, Y0) to (X1, Y1) (8-way, no corner cutting); empty if none. */
	std::vector<std::pair<double, double>> StandPath(const Sailing::FWalkDeck& D, double X0, double Y0, double X1, double Y1)
	{
		int I0, J0, I1, J1;
		D.CellOf(X0, Y0, I0, J0);
		D.CellOf(X1, Y1, I1, J1);
		std::vector<std::pair<double, double>> Out;
		if (!D.InGrid(I0, J0) || !D.InGrid(I1, J1)) return Out;
		std::vector<int> Prev(size_t(D.NX) * D.NY, -2);
		std::deque<int> Queue;
		Queue.push_back(D.Index(I0, J0));
		Prev[D.Index(I0, J0)] = -1;
		while (!Queue.empty())
		{
			const int K = Queue.front();
			Queue.pop_front();
			const int I = K % D.NX, J = K / D.NX;
			if (I == I1 && J == J1) break;
			for (int Dj = -1; Dj <= 1; ++Dj)
			{
				for (int Di = -1; Di <= 1; ++Di)
				{
					const int A = I + Di, B = J + Dj;
					if ((Di == 0 && Dj == 0) || !D.InGrid(A, B)) continue;
					const int N = D.Index(A, B);
					if (Prev[N] != -2 || !D.Stand[N]) continue;
					if (Di != 0 && Dj != 0 && (!D.Stand[D.Index(I + Di, J)] || !D.Stand[D.Index(I, J + Dj)])) continue;
					Prev[N] = K;
					Queue.push_back(N);
				}
			}
		}
		int K = D.Index(I1, J1);
		if (Prev[K] == -2) return Out;
		for (; K >= 0; K = Prev[K]) Out.push_back({ D.X0 + (K % D.NX) * D.Cell, D.Y0 + (K / D.NX) * D.Cell });
		std::reverse(Out.begin(), Out.end());
		return Out;
	}

	/** Steers the walker along a standing path to (X, Y) on his deck, a minute at most. True once he is within 15 cm, or
	 * when he steps onto link Allow facing it; a test failure if he takes any other link, finds no path or sticks. */
	bool WalkTo(FAutomationTestBase& Test, const Sailing::FWalkMap& M, Sailing::FShipWalker& W, double X, double Y, const FString& What, int Allow = -1)
	{
		using namespace Sailing;
		const std::vector<std::pair<double, double>> P = StandPath(M.Decks[W.GetDeck()], W.GetFeet().X, W.GetFeet().Y, X, Y);
		if (P.empty())
		{
			Test.AddError(FString::Printf(TEXT("%s: no standing path on %hs from (%.2f, %.2f) to (%.2f, %.2f)"), *What,
				M.Decks[W.GetDeck()].Name.c_str(), W.GetFeet().X, W.GetFeet().Y, X, Y));
			return false;
		}
		size_t K = 0;
		for (int S = 0; S < 60 * 60; ++S)
		{
			const Vec3 F = W.GetFeet();
			while (K + 1 < P.size() && FMath::Sqrt(FMath::Square(P[K].first - F.X) + FMath::Square(P[K].second - F.Y)) < 0.12) ++K;
			const double Dx = P[K].first - F.X, Dy = P[K].second - F.Y;
			if (K + 1 == P.size() && FMath::Sqrt(Dx * Dx + Dy * Dy) < 0.15) return true;
			const double Turn = FMath::FindDeltaAngleDegrees(W.GetYawDeg(), FMath::RadiansToDegrees(FMath::Atan2(Dy, Dx)));
			FWalkInput In;
			In.LookYawDeg = Turn;
			In.Forward = FMath::Abs(Turn) < 30.0 ? 0.6 : 0.0;
			W.Step(M, In, kUpright, kFrame);
			if (W.GetLink() >= 0 && W.GetLink() == Allow) return true;
			if (W.GetLink() >= 0)
			{
				Test.AddError(FString::Printf(TEXT("%s: took the %hs on the way"), *What, M.Links[W.GetLink()].Name.c_str()));
				return false;
			}
		}
		Test.AddError(FString::Printf(TEXT("%s: stuck at (%.2f, %.2f) on the way to (%.2f, %.2f)"), *What, W.GetFeet().X, W.GetFeet().Y, X, Y));
		return false;
	}

	/** Walks to link L's end on his deck, takes it with Use and climbs it to the other deck. */
	bool TakeLink(FAutomationTestBase& Test, const Sailing::FWalkMap& M, Sailing::FShipWalker& W, int L)
	{
		using namespace Sailing;
		if (L < 0)
		{
			Test.AddError(TEXT("a way between decks is missing"));
			return false;
		}
		const FWalkLink& Link = M.Links[L];
		const FString Name = UTF8_TO_TCHAR(Link.Name.c_str());
		const bool bDown = W.GetDeck() == Link.Upper;
		const Vec3 End = bDown ? Link.Top : Link.Foot;
		if (!WalkTo(Test, M, W, End.X, End.Y, FString::Printf(TEXT("to the %s"), *Name), L)) return false;
		if (W.GetLink() < 0)
		{
			const Vec3 Other = bDown ? Link.Foot : Link.Top;
			FWalkInput Face;
			Face.LookYawDeg = FMath::FindDeltaAngleDegrees(W.GetYawDeg(), FMath::RadiansToDegrees(FMath::Atan2(Other.Y - End.Y, Other.X - End.X)));
			W.Step(M, Face, kUpright, kFrame);
			FWalkInput Use;
			Use.bUse = true;
			W.Step(M, Use, kUpright, kFrame);
		}
		if (!Test.TestEqual(FString::Printf(TEXT("%s: Use takes it"), *Name), W.GetLink(), L)) return false;
		for (int S = 0; S < 60 * 30 && W.GetLink() >= 0; ++S)
		{
			FWalkInput Go;
			Go.Forward = 1.0;
			W.Step(M, Go, kUpright, kFrame);
		}
		const int Target = bDown ? Link.Lower : Link.Upper;
		return Test.TestTrue(FString::Printf(TEXT("%s %s: off it on the %hs"), *Name, bDown ? TEXT("down") : TEXT("up"), M.Decks[Target].Name.c_str()),
			W.GetDeck() == Target && W.GetLink() < 0);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipWalkBluebonnetTest, "SailingSim.ShipWalk.Bluebonnet", ShipWalkFlags)
bool FShipWalkBluebonnetTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	// The J-Class's map (Tools/shipkit/jclass/walk_bluebonnet.py): from the wheel up out of the cockpit, down the doghouse
	// stairs, forward through the saloon, the galley and the fo'c'sle, up the crew's companionway, along the foredeck and
	// back down into the cockpit to the wheel.
	const FString Path = FPaths::ProjectContentDir() / TEXT("TerrainData/Ships/Bluebonnet.walk");
	TArray<uint8> Bytes;
	if (!FFileHelper::LoadFileToArray(Bytes, *Path, FILEREAD_Silent))
	{
		AddInfo(TEXT("no Bluebonnet.walk in the tree yet: skipped"));
		return true;
	}
	FWalkMap M;
	std::string Error;
	if (!TestTrue(TEXT("Bluebonnet.walk parses"), M.Parse(Bytes.GetData(), size_t(Bytes.Num()), &Error))) return false;
	for (const char* Deck : { "Deck", "Cockpit", "Below" }) TestTrue(FString::Printf(TEXT("a %hs deck"), Deck), M.DeckNamed(Deck) >= 0);
	for (const FWalkLink& L : M.Links)
	{
		const FString Name = UTF8_TO_TCHAR(L.Name.c_str());
		TestTrue(FString::Printf(TEXT("%s: its foot is somewhere to stand"), *Name), M.Decks[L.Lower].CanStand(L.Foot.X, L.Foot.Y));
		TestTrue(FString::Printf(TEXT("%s: its top is somewhere to stand"), *Name), M.Decks[L.Upper].CanStand(L.Top.X, L.Top.Y));
	}
	const FWalkSpot* Helm = M.SpotNamed("Helm");
	FShipWalker W;
	if (!TestTrue(TEXT("she has a helm spot to stand on"), Helm != nullptr && W.Reset(M, Helm->Deck, Helm->X, Helm->Y, Helm->YawDeg))) return false;
	auto LinkNamed = [&M](const char* Name) { for (size_t K = 0; K < M.Links.size(); ++K) if (M.Links[K].Name == Name) return int(K); return -1; };
	const bool bRound = TakeLink(*this, M, W, LinkNamed("Cockpit"))
		&& TakeLink(*this, M, W, LinkNamed("Doghouse"))
		&& WalkTo(*this, M, W, -2.0, 0.0, TEXT("the saloon"))
		&& WalkTo(*this, M, W, 3.0, 0.8, TEXT("the galley"))
		&& WalkTo(*this, M, W, 5.3, 0.0, TEXT("the fo'c'sle"))
		&& TakeLink(*this, M, W, LinkNamed("Companionway"))
		&& WalkTo(*this, M, W, 10.0, 1.5, TEXT("forward on deck"))
		&& TakeLink(*this, M, W, LinkNamed("Cockpit"))
		&& WalkTo(*this, M, W, Helm->X, Helm->Y, TEXT("back to the wheel"));
	TestTrue(TEXT("round the boat, deck and below"), bRound);
	return true;
}

#endif
