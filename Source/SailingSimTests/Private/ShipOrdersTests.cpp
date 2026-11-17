#include "Misc/AutomationTest.h"
#include "ShipOrders.h"

#if WITH_DEV_AUTOMATION_TESTS

/**
 * A ship's orders (docs/ship-orders/): every order has its row, call and line; what can be ordered follows the ship's
 * state (the sail plan's manoeuvres, her helmsman, the guns' drill one step at a time); the helm's points; the panel's
 * tabs, rows, the guns' side and the orders given.
 */
namespace ShipOrdersTestsLocal
{
	constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;

	Sailing::FShipOrderContext Underway()
	{
		Sailing::FShipOrderContext C;
		C.bSquareRig = true;
		C.bHasGuns = true;
		C.bHelmsman = true;
		C.TrueWindAngleDeg = 90.0;
		return C;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipOrdersRulesTest, "SailingSim.ShipOrders.Rules", ShipOrdersTestsLocal::Flags)
bool FShipOrdersRulesTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	TestEqual(TEXT("eight sail orders"), int32(ShipOrdersIn(EShipOrderGroup::Sails).size()), 8);
	TestEqual(TEXT("four helm orders"), int32(ShipOrdersIn(EShipOrderGroup::Helm).size()), 4);
	TestEqual(TEXT("six gun orders"), int32(ShipOrdersIn(EShipOrderGroup::Guns).size()), 6);
	for (int32 K = 0; K < int32(EShipOrder::Count); ++K)
	{
		const FShipOrderInfo& I = ShipOrderInfo(EShipOrder(K));
		TestTrue(FString::Printf(TEXT("order %d has its row, call and line"), K), I.Order == EShipOrder(K) && *I.Label && *I.Call && *I.Explain);
		TestEqual(FString::Printf(TEXT("order %d: only the guns take a side"), K), I.bSided, I.Group == EShipOrderGroup::Guns);
	}

	FShipOrderContext C = ShipOrdersTestsLocal::Underway();
	TestNull(TEXT("tack under way"), ShipOrderBlocked(EShipOrder::Tack, EOrderSide::Both, C));
	TestNotNull(TEXT("no fill away unless hove to"), ShipOrderBlocked(EShipOrder::FillAway, EOrderSide::Both, C));
	FShipOrderContext Hove = C;
	Hove.bHoveTo = true;
	TestNotNull(TEXT("no tack while hove to"), ShipOrderBlocked(EShipOrder::Tack, EOrderSide::Both, Hove));
	TestNull(TEXT("fill away while hove to"), ShipOrderBlocked(EShipOrder::FillAway, EOrderSide::Both, Hove));
	FShipOrderContext Busy = C;
	Busy.bManoeuvring = true;
	TestNotNull(TEXT("sail orders wait for a manoeuvre"), ShipOrderBlocked(EShipOrder::MakeSail, EOrderSide::Both, Busy));
	FShipOrderContext NoRig = C;
	NoRig.bSquareRig = false;
	TestNotNull(TEXT("no sail orders without the square rig"), ShipOrderBlocked(EShipOrder::MakeSail, EOrderSide::Both, NoRig));

	// The helm: points of the compass, never closer than she sails or past dead downwind, on her own tack.
	TestEqual(TEXT("luff a point"), HelmTargetAfter(EShipOrder::LuffPoint, 90.0, C), 78.75);
	TestEqual(TEXT("luff a point on port"), HelmTargetAfter(EShipOrder::LuffPoint, -70.0, C), -67.5);
	TestEqual(TEXT("bear away to dead downwind at most"), HelmTargetAfter(EShipOrder::BearAwayPoint, 175.0, C), 180.0);
	TestEqual(TEXT("other orders leave the course"), HelmTargetAfter(EShipOrder::Tack, 90.0, C), 90.0);
	FShipOrderContext Close = C;
	Close.TrueWindAngleDeg = 68.0;
	TestNotNull(TEXT("no luff when close-hauled"), ShipOrderBlocked(EShipOrder::LuffPoint, EOrderSide::Both, Close));
	FShipOrderContext Steering = C;
	Steering.bHelmsman = false;
	TestNotNull(TEXT("no point orders while you steer"), ShipOrderBlocked(EShipOrder::LuffPoint, EOrderSide::Both, Steering));
	TestNull(TEXT("the helmsman takes her"), ShipOrderBlocked(EShipOrder::TakeHelm, EOrderSide::Both, Steering));

	// The guns, a step at a time on each side.
	TestNull(TEXT("cast loose"), ShipOrderBlocked(EShipOrder::CastLoose, EOrderSide::Port, C));
	TestNotNull(TEXT("load before casting loose"), ShipOrderBlocked(EShipOrder::Load, EOrderSide::Port, C));
	TestNotNull(TEXT("fire before running out"), ShipOrderBlocked(EShipOrder::Fire, EOrderSide::Both, C));
	C.Guns[1] = EGunsReady::RunOut;
	TestNull(TEXT("fire the starboard guns"), ShipOrderBlocked(EShipOrder::Fire, EOrderSide::Starboard, C));
	TestNotNull(TEXT("not the port guns"), ShipOrderBlocked(EShipOrder::Fire, EOrderSide::Port, C));
	TestNull(TEXT("both sides: whichever can"), ShipOrderBlocked(EShipOrder::Fire, EOrderSide::Both, C));
	FShipOrderContext Unarmed = C;
	Unarmed.bHasGuns = false;
	TestNotNull(TEXT("no guns, no gun orders"), ShipOrderBlocked(EShipOrder::CastLoose, EOrderSide::Both, Unarmed));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FShipOrdersPanelTest, "SailingSim.ShipOrders.Panel", ShipOrdersTestsLocal::Flags)
bool FShipOrdersPanelTest::RunTest(const FString& Parameters)
{
	using namespace Sailing;
	const FShipOrderContext C = ShipOrdersTestsLocal::Underway();
	FShipOrdersPanel P;
	P.Open();
	FIssuedOrder O;
	TestTrue(TEXT("opens on the sails"), P.IsOpen() && P.GetGroup() == EShipOrderGroup::Sails && P.GetRow() == 0);
	TestTrue(TEXT("make all sail"), P.Select(C, 1.0, O) && O.Order == EShipOrder::MakeSail && O.Time == 1.0);
	P.MoveRow(-1);
	TestEqual(TEXT("up from the top wraps"), P.GetRow(), 7);
	P.MoveGroup(-1);
	TestTrue(TEXT("left from the sails: the guns"), P.GetGroup() == EShipOrderGroup::Guns && P.GetRow() == 0);
	TestTrue(TEXT("the guns' first row is the side"), P.IsSideRow(P.GetGroup(), 0) && P.NumRows(EShipOrderGroup::Guns) == 7);
	TestTrue(TEXT("select steps the side"), !P.Select(C, 2.0, O) && P.GetSide() == EOrderSide::Port && P.GetRefusal().empty());
	P.MoveRow(1);
	TestTrue(TEXT("cast loose the port guns"), P.Select(C, 3.0, O) && O.Order == EShipOrder::CastLoose && O.Side == EOrderSide::Port);
	P.MoveRow(3);
	TestTrue(TEXT("fire is refused, with the reason"), !P.Select(C, 4.0, O) && !P.GetRefusal().empty());
	for (int32 K = 0; K < 6; ++K)
	{
		P.SetGroup(EShipOrderGroup::Sails);
		P.Select(C, 5.0 + K, O);
	}
	TestEqual(TEXT("the last four orders kept"), int32(P.GetHistory().size()), FShipOrdersPanel::MaxHistory);
	P.Toggle();
	TestFalse(TEXT("toggled shut"), P.IsOpen());
	return true;
}

#endif
