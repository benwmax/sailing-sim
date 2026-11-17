#include "ShipOrders.h"

#include <algorithm>
#include <cmath>

namespace Sailing
{
	namespace
	{
		const FShipOrderInfo kOrders[] = {
			{ EShipOrder::MakeSail, EShipOrderGroup::Sails, "Make all sail", "Make all sail!",
				"Every sail set: her best speed in a moderate breeze", false },
			{ EShipOrder::FightingSail, EShipOrderGroup::Sails, "Fighting sail", "Topsails and jibs! Clew up the courses!",
				"Topsails, jibs and spanker only: easy to handle, and the courses out of the guns' smoke", false },
			{ EShipOrder::ShortenSail, EShipOrderGroup::Sails, "Shorten sail", "Hands aloft to reef topsails! In t'gallants and royals!",
				"The light upper sails in and a reef in the topsails, for a rising wind", false },
			{ EShipOrder::FurlAll, EShipOrderGroup::Sails, "Furl all", "Furl all!",
				"Every sail furled on its yard: she drifts", false },
			{ EShipOrder::Tack, EShipOrderGroup::Sails, "Tack", "Ready about! ... Helm's a-lee!",
				"Turn her bow through the wind onto the other tack; she needs good speed to come round", false },
			{ EShipOrder::Wear, EShipOrderGroup::Sails, "Wear ship", "Stand by to wear ship! Up helm!",
				"Turn her stern through the wind onto the other tack: slower than tacking, but sure", false },
			{ EShipOrder::HeaveTo, EShipOrderGroup::Sails, "Heave to", "Back the main topsail! Heave to!",
				"The main topsail backed against the others: she lies nearly still", false },
			{ EShipOrder::FillAway, EShipOrderGroup::Sails, "Fill away", "Fill the main topsail!",
				"Brace the backed sails round to fill again and gather way", false },
			{ EShipOrder::TakeHelm, EShipOrderGroup::Helm, "Helmsman: hold her", "Quartermaster, take the helm! Full and by!",
				"Her helmsman takes the wheel and keeps her at this angle to the wind", false },
			{ EShipOrder::LuffPoint, EShipOrderGroup::Helm, "Luff a point", "Luff a point!",
				"A point (11 degrees) closer to the wind", false },
			{ EShipOrder::BearAwayPoint, EShipOrderGroup::Helm, "Bear away a point", "Keep her away a point!",
				"A point (11 degrees) further off the wind", false },
			{ EShipOrder::MyHelm, EShipOrderGroup::Helm, "I have the helm", "I have the helm!",
				"You take the wheel back from the helmsman", false },
			{ EShipOrder::CastLoose, EShipOrderGroup::Guns, "Cast loose", "Cast loose your guns!",
				"The guns' lashings off, tompions out: ready to load", true },
			{ EShipOrder::Load, EShipOrderGroup::Guns, "Load", "Load with cartridge! Shot your guns!",
				"Powder, wad and shot rammed home", true },
			{ EShipOrder::RunOut, EShipOrderGroup::Guns, "Run out", "Run out your guns!",
				"The crews haul the guns up to the ports, muzzles out", true },
			{ EShipOrder::Fire, EShipOrderGroup::Guns, "Fire", "Fire!",
				"The guns that are run out fire (broadside, ripple or at will), then the crews reload", true },
			{ EShipOrder::CeaseFire, EShipOrderGroup::Guns, "Cease fire", "Cease firing!",
				"No more shots; the crews finish what they are doing", true },
			{ EShipOrder::Secure, EShipOrderGroup::Guns, "Secure the guns", "House your guns! Secure!",
				"The guns run in, housed and lashed, the ports shut", true },
		};
		static_assert(sizeof(kOrders) / sizeof(kOrders[0]) == size_t(EShipOrder::Count), "an info row per order");

		int SideIndex(EOrderSide Side) { return Side == EOrderSide::Starboard ? 1 : 0; }
	}

	const FShipOrderInfo& ShipOrderInfo(EShipOrder Order)
	{
		const size_t K = std::min(size_t(Order), size_t(EShipOrder::Count) - 1);
		return kOrders[K];
	}

	const char* ShipOrderGroupName(EShipOrderGroup Group)
	{
		switch (Group)
		{
		case EShipOrderGroup::Sails: return "Sails";
		case EShipOrderGroup::Helm: return "Helm";
		case EShipOrderGroup::Guns: return "Guns";
		default: return "";
		}
	}

	const char* OrderSideName(EOrderSide Side)
	{
		switch (Side)
		{
		case EOrderSide::Port: return "Port";
		case EOrderSide::Starboard: return "Starboard";
		default: return "Both sides";
		}
	}

	std::vector<EShipOrder> ShipOrdersIn(EShipOrderGroup Group)
	{
		std::vector<EShipOrder> Out;
		for (const FShipOrderInfo& I : kOrders) if (I.Group == Group) Out.push_back(I.Order);
		return Out;
	}

	const char* ShipOrderBlocked(EShipOrder Order, EOrderSide Side, const FShipOrderContext& C)
	{
		const FShipOrderInfo& I = ShipOrderInfo(Order);
		if (I.Group == EShipOrderGroup::Sails)
		{
			if (!C.bSquareRig) return "Her sails can't be ordered yet";
			if (!C.bManoeuvres && (Order == EShipOrder::Tack || Order == EShipOrder::Wear || Order == EShipOrder::HeaveTo || Order == EShipOrder::FillAway))
				return "The crew aren't drilled for that yet";
			if (C.bManoeuvring && Order != EShipOrder::FillAway) return "The crew are still at the last manoeuvre";
			if (Order == EShipOrder::FillAway && !C.bHoveTo) return "She isn't hove to";
			if (Order == EShipOrder::HeaveTo && C.bHoveTo) return "She is already hove to";
			if (Order == EShipOrder::Tack && C.bHoveTo) return "Fill away first: she needs way on to tack";
			return nullptr;
		}
		if (I.Group == EShipOrderGroup::Helm)
		{
			if (Order == EShipOrder::TakeHelm && C.bHelmsman) return "The helmsman already has her";
			if (Order == EShipOrder::MyHelm && !C.bHelmsman) return "You have the helm";
			if ((Order == EShipOrder::LuffPoint || Order == EShipOrder::BearAwayPoint) && !C.bHelmsman) return "You are steering: tell the helmsman to take her first";
			if (Order == EShipOrder::LuffPoint && std::abs(C.TrueWindAngleDeg) < C.ClosestTwaDeg + 1.0) return "She is as close to the wind as she will sail";
			if (Order == EShipOrder::BearAwayPoint && std::abs(C.TrueWindAngleDeg) > 179.0) return "She is dead before the wind";
			return nullptr;
		}
		// Guns: a side, or both (an order to both goes where it can be carried out on either).
		if (!C.bHasGuns) return "She has no guns";
		auto Can = [&C, Order](int S) -> const char*
		{
			const EGunsReady G = C.Guns[S];
			switch (Order)
			{
			case EShipOrder::CastLoose: return G == EGunsReady::Housed ? nullptr : "Already cast loose";
			case EShipOrder::Load: return G == EGunsReady::Housed ? "Cast loose first" : (G == EGunsReady::CastLoose ? nullptr : "Already loaded");
			case EShipOrder::RunOut: return G == EGunsReady::Housed ? "Cast loose first" : (G == EGunsReady::CastLoose ? "Load first" : (G == EGunsReady::Loaded ? nullptr : "Already run out"));
			case EShipOrder::Fire: return G == EGunsReady::RunOut ? nullptr : "Run out first";
			case EShipOrder::CeaseFire: return C.bFiring[S] ? nullptr : "They aren't firing";
			case EShipOrder::Secure: return G == EGunsReady::Housed ? "Already secured" : nullptr;
			default: return "Not a gun order";
			}
		};
		if (Side != EOrderSide::Both) return Can(SideIndex(Side));
		const char* Port = Can(0);
		const char* Stbd = Can(1);
		return Port && Stbd ? Port : nullptr;
	}

	EGunsReady GunsReadyFor(const FCannonSideStatus& Status)
	{
		auto RankOf = [](EGunState S) -> int
		{
			switch (S)
			{
			case EGunState::Housed: case EGunState::ClosingLid: case EGunState::Securing: return 0;
			case EGunState::CastingLoose: case EGunState::Waiting: case EGunState::Sponging: case EGunState::Loading: return 1;
			case EGunState::Loaded: case EGunState::OpeningLid: case EGunState::RunningOut: case EGunState::RunningIn: return 2;
			default: return 3;   // Ready, Lock, Recoil, Spent: out, or just fired from out
			}
		};
		int Least = 3;
		bool bAny = false;
		for (int K = 0; K < int(EGunState::Count); ++K)
		{
			if (Status.ByState[K] <= 0) continue;
			bAny = true;
			Least = std::min(Least, RankOf(EGunState(K)));
		}
		return bAny ? EGunsReady(Least) : EGunsReady::Housed;
	}

	ECannonOrder CannonOrderFor(EShipOrder Order)
	{
		switch (Order)
		{
		case EShipOrder::Load: return ECannonOrder::Load;
		case EShipOrder::RunOut: return ECannonOrder::RunOut;
		case EShipOrder::Fire: return ECannonOrder::Fire;
		case EShipOrder::CeaseFire: return ECannonOrder::CeaseFire;
		case EShipOrder::Secure: return ECannonOrder::Secure;
		default: return ECannonOrder::CastLoose;
		}
	}

	ECannonSide CannonSideFor(EOrderSide Side)
	{
		return Side == EOrderSide::Port ? ECannonSide::Port : (Side == EOrderSide::Starboard ? ECannonSide::Starboard : ECannonSide::Both);
	}

	bool ApplySailPlan(EShipOrder Order, const FBoatConfig& Config, FBoatControls& Controls)
	{
		if (!Config.HasSquareRig()) return false;
		if (Order != EShipOrder::MakeSail && Order != EShipOrder::FightingSail && Order != EShipOrder::ShortenSail && Order != EShipOrder::FurlAll) return false;
		const int N = std::min(int(Config.Square.Sails.size()), kMaxSquareSails);
		for (int K = 0; K < N; ++K)
		{
			const ESquareSailKind Kind = Config.Square.Sails[size_t(K)].Kind;
			const bool bUpper = Kind == ESquareSailKind::Topgallant || Kind == ESquareSailKind::Royal;
			switch (Order)
			{
			case EShipOrder::MakeSail:
				Controls.SquareSet[K] = ESailSet::Set;
				Controls.SquareReef[K] = 0;
				break;
			case EShipOrder::FightingSail:
				// Topsails only: the courses clewed up (hanging from their yards, ready to set again), the light sails furled.
				Controls.SquareSet[K] = Kind == ESquareSailKind::Topsail ? ESailSet::Set : (Kind == ESquareSailKind::Course ? ESailSet::Clewed : ESailSet::Furled);
				break;
			case EShipOrder::ShortenSail:
				// The light sails in, a reef in the topsails; the courses as they were.
				if (bUpper) Controls.SquareSet[K] = ESailSet::Furled;
				if (Kind == ESquareSailKind::Topsail && !Config.Square.Sails[size_t(K)].ReefAreaFraction.empty()) Controls.SquareReef[K] = std::max<unsigned char>(Controls.SquareReef[K], 1);
				break;
			default:
				Controls.SquareSet[K] = ESailSet::Furled;
				break;
			}
		}
		// Fighting sail keeps the jibs and spanker (she steers by them) and hauls the staysails down; shortening sail leaves
		// the fore-and-aft sails as they are.
		if (Order != EShipOrder::ShortenSail)
		{
			Controls.bMainDown = Order == EShipOrder::FurlAll;
			Controls.bJibDown = Order == EShipOrder::FurlAll;
			Controls.bStaysailDown = Order == EShipOrder::FurlAll || Order == EShipOrder::FightingSail;
		}
		return true;
	}

	double HelmTargetAfter(EShipOrder Order, double TargetTwaDeg, const FShipOrderContext& C)
	{
		if (Order != EShipOrder::LuffPoint && Order != EShipOrder::BearAwayPoint) return TargetTwaDeg;
		const double Sign = TargetTwaDeg < 0.0 ? -1.0 : 1.0;
		const double Off = std::abs(TargetTwaDeg) + (Order == EShipOrder::LuffPoint ? -kCompassPointDeg : kCompassPointDeg);
		return Sign * std::clamp(Off, C.ClosestTwaDeg, 180.0);
	}

	int FShipOrdersPanel::NumRows(EShipOrderGroup InGroup) const
	{
		return int(ShipOrdersIn(InGroup).size()) + (InGroup == EShipOrderGroup::Guns ? 1 : 0);
	}

	bool FShipOrdersPanel::RowOrder(EShipOrderGroup InGroup, int InRow, EShipOrder& Out) const
	{
		const std::vector<EShipOrder> Orders = ShipOrdersIn(InGroup);
		const int K = InRow - (InGroup == EShipOrderGroup::Guns ? 1 : 0);
		if (K < 0 || K >= int(Orders.size())) return false;
		Out = Orders[size_t(K)];
		return true;
	}

	void FShipOrdersPanel::MoveRow(int Delta)
	{
		const int N = NumRows(Group);
		if (N <= 0) return;
		Row = ((Row + Delta) % N + N) % N;
		Refusal.clear();
	}

	void FShipOrdersPanel::MoveGroup(int Delta)
	{
		const int N = int(EShipOrderGroup::Count);
		SetGroup(EShipOrderGroup(((int(Group) + Delta) % N + N) % N));
	}

	void FShipOrdersPanel::SetGroup(EShipOrderGroup InGroup)
	{
		if (InGroup >= EShipOrderGroup::Count) return;
		Group = InGroup;
		Row = 0;
		Refusal.clear();
	}

	bool FShipOrdersPanel::Select(const FShipOrderContext& Context, double Now, FIssuedOrder& Out)
	{
		Refusal.clear();
		if (IsSideRow(Group, Row))
		{
			Side = EOrderSide((int(Side) + 1) % 3);
			return false;
		}
		EShipOrder Order = EShipOrder::MakeSail;
		if (!RowOrder(Group, Row, Order)) return false;
		const EOrderSide OrderSide = ShipOrderInfo(Order).bSided ? Side : EOrderSide::Both;
		if (const char* Why = ShipOrderBlocked(Order, OrderSide, Context))
		{
			Refusal = Why;
			return false;
		}
		Out.Order = Order;
		Out.Side = OrderSide;
		Out.Time = Now;
		History.push_back(Out);
		if (History.size() > size_t(MaxHistory)) History.erase(History.begin());
		return true;
	}
}
