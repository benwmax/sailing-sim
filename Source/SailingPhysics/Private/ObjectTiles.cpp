#include "ObjectTiles.h"

#include <algorithm>
#include <cmath>
#include <utility>

namespace Sailing
{
	FObjectRing ObjectRingForCull(double CullM, const FObjectRing& NoCull)
	{
		if (!(CullM > 0.0)) return NoCull;
		FObjectRing R;
		R.LoadM = CullM + 1000.0;
		R.KeepM = CullM + 3000.0;
		return R;
	}

	void FObjectCells::CellOf(double X, double Y, int& Row, int& Col) const
	{
		Row = int(std::floor(X / CellM));
		Col = int(std::floor(Y / CellM));
	}

	int FObjectCells::Add(double X, double Y)
	{
		int R = 0, C = 0;
		CellOf(X, Y, R, C);
		const auto It = ByCell.find(Key(R, C));
		if (It != ByCell.end()) return It->second;
		const int Id = int(Rows.size());
		Rows.push_back(R);
		Cols.push_back(C);
		ByCell.emplace(Key(R, C), Id);
		return Id;
	}

	int FObjectCells::Find(int Row, int Col) const
	{
		const auto It = ByCell.find(Key(Row, Col));
		return It == ByCell.end() ? -1 : It->second;
	}

	double FObjectCells::DistanceTo(int Id, double X, double Y) const
	{
		const double X0 = Rows[size_t(Id)] * CellM, Y0 = Cols[size_t(Id)] * CellM;
		const double DX = std::max({ X0 - X, 0.0, X - (X0 + CellM) });
		const double DY = std::max({ Y0 - Y, 0.0, Y - (Y0 + CellM) });
		return std::sqrt(DX * DX + DY * DY);
	}

	void PlanObjectCells(const FObjectCells& Cells, const std::vector<uint8_t>& Made, double X, double Y,
		const FObjectRing& Ring, int MaxMake, std::vector<int>& OutMake, std::vector<int>& OutDrop)
	{
		OutMake.clear();
		OutDrop.clear();
		std::vector<std::pair<double, int>> Wanted;
		for (int K = 0; K < Cells.Num(); ++K)
		{
			const double D = Cells.DistanceTo(K, X, Y);
			const bool bMade = K < int(Made.size()) && Made[size_t(K)] != 0;
			if (bMade && D > Ring.KeepM) OutDrop.push_back(K);
			else if (!bMade && D <= Ring.LoadM) Wanted.push_back({ D, K });
		}
		std::sort(Wanted.begin(), Wanted.end());
		for (const std::pair<double, int>& W : Wanted)
		{
			if (MaxMake >= 0 && int(OutMake.size()) >= MaxMake) break;
			OutMake.push_back(W.second);
		}
	}

	int FSlotPool::Acquire(bool& bReused)
	{
		++Live;
		if (!Free.empty())
		{
			const int Slot = Free.back();
			Free.pop_back();
			InUse[size_t(Slot)] = 1;
			bReused = true;
			++Reused;
			return Slot;
		}
		bReused = false;
		InUse.push_back(1);
		return int(InUse.size()) - 1;
	}

	void FSlotPool::Release(int Slot)
	{
		if (Slot < 0 || Slot >= int(InUse.size()) || !InUse[size_t(Slot)]) return;
		InUse[size_t(Slot)] = 0;
		Free.push_back(Slot);
		--Live;
	}
}
