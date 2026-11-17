#pragma once

#include "SailingPhysicsApi.h"

#include <cstdint>
#include <string>
#include <vector>

namespace Sailing
{
	/**
	 * A ship's orders (docs/ship-orders/): what the player, as her captain, tells the crew to do, grouped as the orders
	 * panel shows them (sails, helm, guns), each with the call a captain of the period would give and a plain line on what
	 * it does. Plain logic for the panel and the tests: the game gives each order to whoever carries it out (the square rig's
	 * manoeuvres, her helmsman, the gun battery) and fills FShipOrderContext so the panel knows what can be ordered now.
	 */
	enum class EShipOrderGroup : uint8_t { Sails, Helm, Guns, Count };

	enum class EShipOrder : uint8_t
	{
		// Sails (the square rig's sail plans and manoeuvres)
		MakeSail,        // every sail set
		FightingSail,    // topsails, jibs and spanker; the courses clewed up (out of the way of the guns' smoke and fire)
		ShortenSail,     // topgallants and royals in, a reef in the topsails
		FurlAll,         // everything furled
		Tack,            // through the wind
		Wear,            // round before the wind
		HeaveTo,         // the main topsail backed: she lies nearly still
		FillAway,        // fill the backed sails and gather way again
		// Helm (her helmsman)
		TakeHelm,        // the helmsman takes the wheel and holds her wind angle
		LuffPoint,       // a point (11.25 deg) closer to the wind
		BearAwayPoint,   // a point further off it
		MyHelm,          // the captain takes the wheel back
		// Guns (the battery: both sides or one)
		CastLoose,
		Load,
		RunOut,
		Fire,
		CeaseFire,
		Secure,
		Count
	};

	enum class EOrderSide : uint8_t { Port, Starboard, Both };

	struct SAILINGPHYSICS_API FShipOrderInfo
	{
		EShipOrder Order = EShipOrder::MakeSail;
		EShipOrderGroup Group = EShipOrderGroup::Sails;
		const char* Label = "";     // the panel's row ("Make all sail")
		const char* Call = "";      // what the captain calls ("Make all sail!")
		const char* Explain = "";   // UI Helpful's line on what it does
		bool bSided = false;        // takes a side (the guns)
	};

	SAILINGPHYSICS_API const FShipOrderInfo& ShipOrderInfo(EShipOrder Order);
	SAILINGPHYSICS_API const char* ShipOrderGroupName(EShipOrderGroup Group);
	SAILINGPHYSICS_API const char* OrderSideName(EOrderSide Side);
	/** The orders in a group, in the panel's order. */
	SAILINGPHYSICS_API std::vector<EShipOrder> ShipOrdersIn(EShipOrderGroup Group);

	/** A point of the compass: the helm's orders turn her by one. */
	constexpr double kCompassPointDeg = 11.25;

	/** How the battery's guns stand on one side (the least ready gun on it), for what can be ordered next. */
	enum class EGunsReady : uint8_t { Housed, CastLoose, Loaded, RunOut };

	/** What she can do now: the game fills it each frame from the boat, her helmsman and the battery. */
	struct SAILINGPHYSICS_API FShipOrderContext
	{
		bool bSquareRig = false;       // the square rig's sail orders are carried out (the physics has them)
		bool bManoeuvring = false;     // a tack, a wear or heaving to under way: the sail orders wait for it
		bool bHoveTo = false;
		bool bHelmsman = false;        // her helmsman has the wheel (the captain isn't steering)
		bool bHasGuns = false;
		EGunsReady Guns[2] = { EGunsReady::Housed, EGunsReady::Housed };   // port, starboard
		bool bFiring[2] = { false, false };
		double TrueWindAngleDeg = 0.0; // + wind from starboard
		double ClosestTwaDeg = 67.5;   // the closest she sails to the wind (six points for a frigate)
	};

	/** Why an order can't be given now, or nullptr when it can. */
	SAILINGPHYSICS_API const char* ShipOrderBlocked(EShipOrder Order, EOrderSide Side, const FShipOrderContext& Context);

	/** The helmsman's new wind angle after a helm order (signed like the TWA; held between the closest she sails and dead
	 *  downwind, on the same tack). Other orders leave it. */
	SAILINGPHYSICS_API double HelmTargetAfter(EShipOrder Order, double TargetTwaDeg, const FShipOrderContext& Context);

	struct SAILINGPHYSICS_API FIssuedOrder
	{
		EShipOrder Order = EShipOrder::MakeSail;
		EOrderSide Side = EOrderSide::Both;
		double Time = 0.0;
	};

	/**
	 * The orders panel's state: open or shut, which group's tab, which row, and (on the guns' tab) which side. Up and down
	 * move the row, left and right the tab; on the guns' tab the first row is the side, which Select steps (port,
	 * starboard, both). Select gives the row's order when it can be given, else keeps the reason (GetRefusal).
	 */
	class SAILINGPHYSICS_API FShipOrdersPanel
	{
	public:
		static constexpr int MaxHistory = 4;

		void Open() { bOpen = true; Refusal.clear(); }
		void Close() { bOpen = false; }
		void Toggle() { if (bOpen) Close(); else Open(); }
		bool IsOpen() const { return bOpen; }

		EShipOrderGroup GetGroup() const { return Group; }
		int GetRow() const { return Row; }
		EOrderSide GetSide() const { return Side; }
		/** Rows on the group's tab (the guns' tab has the side first). */
		int NumRows(EShipOrderGroup InGroup) const;
		/** The row's order; false for the guns' side row. */
		bool RowOrder(EShipOrderGroup InGroup, int InRow, EShipOrder& Out) const;
		bool IsSideRow(EShipOrderGroup InGroup, int InRow) const { return InGroup == EShipOrderGroup::Guns && InRow == 0; }

		void MoveRow(int Delta);
		void MoveGroup(int Delta);
		void SetGroup(EShipOrderGroup InGroup);
		/** The row's order, if it can be given now (Out, at Now); false for the side row (stepped) or a refused order. */
		bool Select(const FShipOrderContext& Context, double Now, FIssuedOrder& Out);
		/** Why the last Select gave nothing ("" after an order or a side step). */
		const std::string& GetRefusal() const { return Refusal; }
		/** The orders given, latest last (at most MaxHistory). */
		const std::vector<FIssuedOrder>& GetHistory() const { return History; }

	private:
		bool bOpen = false;
		EShipOrderGroup Group = EShipOrderGroup::Sails;
		int Row = 0;
		EOrderSide Side = EOrderSide::Both;
		std::string Refusal;
		std::vector<FIssuedOrder> History;
	};
}
