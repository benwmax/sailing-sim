#include "LakeTerrain.h"
#include <cstring>

namespace Sailing
{
	namespace
	{
		template <typename T>
		T ReadLE(const uint8_t* P) { T V; std::memcpy(&V, P, sizeof(T)); return V; }
	}

	bool FLakeTerrain::LoadHeight(const uint8_t* Data, size_t Size)
	{
		const size_t Header = 4 + 4 * 3 + 4 * 4;
		if (Size < Header || std::memcmp(Data, "SSHT", 4) != 0) return false;
		const uint32_t Version = ReadLE<uint32_t>(Data + 4);
		const int NX = int(ReadLE<uint32_t>(Data + 8));
		const int NY = int(ReadLE<uint32_t>(Data + 12));
		if (Version != 1 || NX <= 1 || NY <= 1 || Size < Header + size_t(NX) * NY * 2) return false;
		Cell = ReadLE<float>(Data + 16);
		OriginX = ReadLE<float>(Data + 20);
		OriginY = ReadLE<float>(Data + 24);
		Unit = ReadLE<float>(Data + 28);
		Rows = NY;
		Cols = NX;
		Heights.resize(size_t(NX) * NY);
		std::memcpy(Heights.data(), Data + Header, Heights.size() * 2);
		return true;
	}

	bool FLakeTerrain::LoadTrees(const uint8_t* Data, size_t Size)
	{
		const size_t Header = 4 + 4 * 3 + 4 * 3;
		if (Size < Header || std::memcmp(Data, "SSTR", 4) != 0) return false;
		TreeCols = int(ReadLE<uint32_t>(Data + 8));
		TreeRows = int(ReadLE<uint32_t>(Data + 12));
		TreeCell = ReadLE<float>(Data + 16);
		TreeOriginX = ReadLE<float>(Data + 20);
		TreeOriginY = ReadLE<float>(Data + 24);
		if (Size < Header + size_t(TreeRows) * TreeCols) { TreeRows = TreeCols = 0; return false; }
		Trees.assign(Data + Header, Data + Header + size_t(TreeRows) * TreeCols);
		return true;
	}

	void FLakeTerrain::InitSynthetic(int InRows, int InCols, double InCell, double InOriginX, double InOriginY, const std::vector<float>& InHeights)
	{
		Rows = InRows;
		Cols = InCols;
		Cell = InCell;
		OriginX = InOriginX;
		OriginY = InOriginY;
		Unit = 0.01;
		Heights.resize(size_t(Rows) * Cols);
		for (size_t I = 0; I < Heights.size(); ++I)
		{
			Heights[I] = int16_t(Clamp(std::round(InHeights[I] / Unit), -32000.0, 32000.0));
		}
	}

	double FLakeTerrain::NodeHeight(int Row, int Col) const
	{
		Row = Row < 0 ? 0 : (Row >= Rows ? Rows - 1 : Row);
		Col = Col < 0 ? 0 : (Col >= Cols ? Cols - 1 : Col);
		return Heights[size_t(Row) * Cols + Col] * Unit + LevelBelowPool;
	}

	double FLakeTerrain::HeightAt(double X, double Y) const
	{
		if (Rows == 0) return -1000.0; // no terrain: open water everywhere
		const double R = (X - OriginX) / Cell, C = (Y - OriginY) / Cell;
		if (R < -1.0 || C < -1.0 || R > Rows || C > Cols) return 50.0; // off the map: land
		const int R0 = int(std::floor(R)), C0 = int(std::floor(C));
		const double FR = R - R0, FC = C - C0;
		const double H00 = NodeHeight(R0, C0), H01 = NodeHeight(R0, C0 + 1), H10 = NodeHeight(R0 + 1, C0), H11 = NodeHeight(R0 + 1, C0 + 1);
		return Lerp(Lerp(H00, H01, FC), Lerp(H10, H11, FC), FR);
	}

	double FLakeTerrain::CanopyAt(double X, double Y) const
	{
		if (TreeRows == 0) return 0.0;
		const int R = int((X - TreeOriginX) / TreeCell), C = int((Y - TreeOriginY) / TreeCell);
		if (R < 0 || C < 0 || R >= TreeRows || C >= TreeCols) return 0.0;
		return Trees[size_t(R) * TreeCols + C] / 255.0 * 12.0;
	}

	double FLakeTerrain::FetchToward(double X, double Y, double FromRadians, double MaxDistance) const
	{
		if (Rows == 0) return MaxDistance;
		const double DX = std::cos(FromRadians), DY = std::sin(FromRadians);
		const double Step = Cell;
		for (double S = Step; S < MaxDistance; S += Step)
		{
			if (HeightAt(X + DX * S, Y + DY * S) > 0.0) return S;
		}
		return MaxDistance;
	}

	void FShelterMap::Build(const FLakeTerrain& Terrain, double InFromRadians, double InCell)
	{
		FromRadians = InFromRadians;
		Cell = InCell;
		if (!Terrain.IsValid()) { Rows = Cols = 0; Factor.clear(); return; }
		OriginX = Terrain.GetOriginX();
		OriginY = Terrain.GetOriginY();
		Rows = int(Terrain.GetRows() * Terrain.GetCell() / Cell) + 1;
		Cols = int(Terrain.GetCols() * Terrain.GetCell() / Cell) + 1;
		Factor.assign(size_t(Rows) * Cols, 1.0f);
		const double DX = std::cos(FromRadians), DY = std::sin(FromRadians);
		for (int R = 0; R < Rows; ++R)
		{
			for (int C = 0; C < Cols; ++C)
			{
				const double X = OriginX + R * Cell, Y = OriginY + C * Cell;
				if (Terrain.HeightAt(X, Y) > 0.0) continue; // only water matters
				double Reduction = 0.0;
				for (double S = 20.0; S <= 700.0; S += 20.0)
				{
					const double PX = X + DX * S, PY = Y + DY * S;
					const double Top = std::max(Terrain.HeightAt(PX, PY), 0.0) + (Terrain.HeightAt(PX, PY) > 0.0 ? Terrain.CanopyAt(PX, PY) : 0.0);
					if (Top < 1.0) continue;
					// Wake behind an obstacle of height Top: strongest within a few heights, recovered by about 25 heights.
					const double Ratio = S / Top;
					Reduction = std::max(Reduction, 0.65 * (1.0 - SmoothStep(2.0, 25.0, Ratio)));
				}
				Factor[size_t(R) * Cols + C] = float(1.0 - Reduction);
			}
		}
	}

	double FShelterMap::FactorAt(double X, double Y) const
	{
		if (Rows == 0) return 1.0;
		const double R = (X - OriginX) / Cell, C = (Y - OriginY) / Cell;
		const int R0 = int(std::floor(R)), C0 = int(std::floor(C));
		if (R0 < 0 || C0 < 0 || R0 + 1 >= Rows || C0 + 1 >= Cols) return 1.0;
		const double FR = R - R0, FC = C - C0;
		auto F = [&](int RR, int CC) { return double(Factor[size_t(RR) * Cols + CC]); };
		return Lerp(Lerp(F(R0, C0), F(R0, C0 + 1), FC), Lerp(F(R0 + 1, C0), F(R0 + 1, C0 + 1), FC), FR);
	}
}
