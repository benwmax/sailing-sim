#include "LakeTerrain.h"
#include <cmath>
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

	bool FLakeTerrain::LoadDetail(const uint8_t* Data, size_t Size)
	{
		const size_t Header = 4 + 4 * 3 + 4 * 4;
		if (Size < Header || std::memcmp(Data, "SSDT", 4) != 0 || ReadLE<uint32_t>(Data + 4) != 1 || Rows == 0) return false;
		const int Tile = int(ReadLE<uint32_t>(Data + 8));
		const size_t Count = ReadLE<uint32_t>(Data + 12);
		const size_t Nodes = size_t(Tile + 1) * (Tile + 1);
		if (Tile < 2 || Size < Header + Count * (8 + Nodes * 2)) return false;
		DetailTile = Tile;
		DetailCell = ReadLE<float>(Data + 16);
		DetailOriginX = ReadLE<float>(Data + 20);
		DetailOriginY = ReadLE<float>(Data + 24);
		DetailUnit = ReadLE<float>(Data + 28);
		const double Span = Tile * DetailCell;
		DetailRows = int(std::ceil((OriginX + (Rows - 1) * Cell - DetailOriginX) / Span)) + 1;
		DetailCols = int(std::ceil((OriginY + (Cols - 1) * Cell - DetailOriginY) / Span)) + 1;
		DetailIndex.assign(size_t(DetailRows) * DetailCols, -1);
		const uint8_t* P = Data + Header;
		for (size_t K = 0; K < Count; ++K)
		{
			const int R = ReadLE<int32_t>(P + 8 * K), C = ReadLE<int32_t>(P + 8 * K + 4);
			if (R >= 0 && C >= 0 && R < DetailRows && C < DetailCols) DetailIndex[size_t(R) * DetailCols + C] = int32_t(K);
		}
		Detail.resize(Count * Nodes);
		std::memcpy(Detail.data(), P + 8 * Count, Detail.size() * 2);
		return true;
	}

	int FLakeTerrain::DetailTileAt(double X, double Y, double& U, double& V) const
	{
		if (Detail.empty()) return -1;
		const double Span = DetailTile * DetailCell;
		const double TX = (X - DetailOriginX) / Span, TY = (Y - DetailOriginY) / Span;
		if (TX < 0.0 || TY < 0.0) return -1;
		const int R = int(TX), C = int(TY);
		if (R >= DetailRows || C >= DetailCols) return -1;
		U = (TX - R) * DetailTile;
		V = (TY - C) * DetailTile;
		return DetailIndex[size_t(R) * DetailCols + C];
	}

	bool FLakeTerrain::DetailHeightAt(double X, double Y, double& Height) const
	{
		double U, V;
		const int Index = DetailTileAt(X, Y, U, V);
		if (Index < 0) return false;
		const int N = DetailTile + 1;
		const int R0 = int(U) < DetailTile ? int(U) : DetailTile - 1, C0 = int(V) < DetailTile ? int(V) : DetailTile - 1;
		const double FR = U - R0, FC = V - C0;
		const int16_t* T = Detail.data() + size_t(Index) * N * N;
		const double H00 = T[R0 * N + C0], H01 = T[R0 * N + C0 + 1], H10 = T[(R0 + 1) * N + C0], H11 = T[(R0 + 1) * N + C0 + 1];
		Height = Lerp(Lerp(H00, H01, FC), Lerp(H10, H11, FC), FR) * DetailUnit + LevelBelowPool;
		return true;
	}

	bool FLakeTerrain::HasDetailIn(double MinX, double MinY, double MaxX, double MaxY) const
	{
		if (Detail.empty()) return false;
		const double Span = DetailTile * DetailCell;
		const int R0 = int(std::floor((MinX - DetailOriginX) / Span)), R1 = int(std::floor((MaxX - DetailOriginX) / Span));
		const int C0 = int(std::floor((MinY - DetailOriginY) / Span)), C1 = int(std::floor((MaxY - DetailOriginY) / Span));
		for (int R = R0 < 0 ? 0 : R0; R <= R1 && R < DetailRows; ++R)
			for (int C = C0 < 0 ? 0 : C0; C <= C1 && C < DetailCols; ++C)
				if (DetailIndex[size_t(R) * DetailCols + C] >= 0) return true;
		return false;
	}

	void FLakeTerrain::InitSyntheticTrees(int InRows, int InCols, double InCell, double InOriginX, double InOriginY, const std::vector<uint8_t>& Density)
	{
		TreeRows = InRows;
		TreeCols = InCols;
		TreeCell = InCell;
		TreeOriginX = InOriginX;
		TreeOriginY = InOriginY;
		Trees = Density;
		Trees.resize(size_t(TreeRows) * TreeCols, 0);
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
		double Fine;
		if (DetailHeightAt(X, Y, Fine)) return Fine;
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

	double FShelterMap::LeeDeficit(double Ratio)
	{
		// Shelterbelt and escarpment wakes: deepest within about 4 heights, still a quarter down at 20, gone by 30.
		return 0.62 * (1.0 - SmoothStep(4.0, 30.0, Ratio));
	}

	double FShelterMap::OpenWaterBuild(double FetchMeters)
	{
		// The internal boundary layer from a land-water roughness step: the 10 m wind climbs from about 80 % of the
		// open-water value at the shore with an e-folding fetch of 800 m (lake and coastal mast studies).
		return 0.8 + 0.2 * (1.0 - std::exp(-std::max(FetchMeters, 0.0) / 800.0));
	}

	void FShelterMap::Build(const FLakeTerrain& Terrain, double InFromRadians, double InCell, const std::vector<FShelterObstacle>* Obstacles)
	{
		FromRadians = InFromRadians;
		Cell = InCell;
		if (!Terrain.IsValid()) { Rows = Cols = 0; Lee.clear(); Building.clear(); return; }
		OriginX = Terrain.GetOriginX();
		OriginY = Terrain.GetOriginY();
		Rows = int(Terrain.GetRows() * Terrain.GetCell() / Cell) + 1;
		Cols = int(Terrain.GetCols() * Terrain.GetCell() / Cell) + 1;
		Lee.assign(size_t(Rows) * Cols, 1.0f);
		Building.assign(size_t(Rows) * Cols, 1.0f);
		// Houses (and anything else) rasterised to the march's resolution: the highest top in each 20 m cell.
		constexpr double Step = 20.0;
		const int HRows = int(Rows * Cell / Step) + 2, HCols = int(Cols * Cell / Step) + 2;
		std::vector<float> Extra;
		if (Obstacles && !Obstacles->empty())
		{
			Extra.assign(size_t(HRows) * HCols, 0.0f);
			for (const FShelterObstacle& O : *Obstacles)
			{
				const int R0 = int(std::floor((O.X - O.Radius - OriginX) / Step)), R1 = int(std::floor((O.X + O.Radius - OriginX) / Step));
				const int C0 = int(std::floor((O.Y - O.Radius - OriginY) / Step)), C1 = int(std::floor((O.Y + O.Radius - OriginY) / Step));
				for (int R = std::max(R0, 0); R <= std::min(R1, HRows - 1); ++R)
					for (int C = std::max(C0, 0); C <= std::min(C1, HCols - 1); ++C)
						Extra[size_t(R) * HCols + C] = std::max(Extra[size_t(R) * HCols + C], float(O.Top));
			}
		}
		auto ExtraAt = [&](double X, double Y)
		{
			if (Extra.empty()) return 0.0;
			const int R = int(std::floor((X - OriginX) / Step)), C = int(std::floor((Y - OriginY) / Step));
			return R < 0 || C < 0 || R >= HRows || C >= HCols ? 0.0 : double(Extra[size_t(R) * HCols + C]);
		};
		const double DX = std::cos(FromRadians), DY = std::sin(FromRadians);
		for (int R = 0; R < Rows; ++R)
		{
			for (int C = 0; C < Cols; ++C)
			{
				const double X = OriginX + R * Cell, Y = OriginY + C * Cell;
				if (Terrain.HeightAt(X, Y) > 0.0) continue; // only water matters
				// Upwind: the lee of anything within 30 heights (a 30 m bluff with its trees reaches 900 m), and the first land.
				double Reduction = 0.0, Fetch = -1.0;
				const double MaxX = OriginX + Terrain.GetRows() * Terrain.GetCell(), MaxY = OriginY + Terrain.GetCols() * Terrain.GetCell();
				for (double S = Step; S <= 3000.0; S += (S < 1000.0 ? Step : 2.0 * Step))
				{
					const double PX = X + DX * S, PY = Y + DY * S;
					// Past the edge of the bake: nothing more is known (its "high land" is a stand-in, not a hill).
					if (PX < OriginX || PY < OriginY || PX > MaxX || PY > MaxY)
					{
						if (Fetch < 0.0) Fetch = S;
						break;
					}
					const double Ground = Terrain.HeightAt(PX, PY);
					if (Ground > 0.0 && Fetch < 0.0) Fetch = S;
					if (S > 1000.0)
					{
						if (Fetch >= 0.0) break;
						continue;
					}
					const double Top = std::max({ Ground, 0.0, ExtraAt(PX, PY) }) + (Ground > 0.0 ? Terrain.CanopyAt(PX, PY) : 0.0);
					if (Top < 1.0) continue;
					Reduction = std::max(Reduction, LeeDeficit(S / Top));
				}
				Lee[size_t(R) * Cols + C] = float(1.0 - Reduction);
				Building[size_t(R) * Cols + C] = float(OpenWaterBuild(Fetch < 0.0 ? 1e9 : Fetch));
			}
		}
	}

	double FShelterMap::Sample(const std::vector<float>& Grid, double X, double Y) const
	{
		if (Rows == 0) return 1.0;
		const double R = (X - OriginX) / Cell, C = (Y - OriginY) / Cell;
		const int R0 = int(std::floor(R)), C0 = int(std::floor(C));
		if (R0 < 0 || C0 < 0 || R0 + 1 >= Rows || C0 + 1 >= Cols) return 1.0;
		const double FR = R - R0, FC = C - C0;
		auto F = [&](int RR, int CC) { return double(Grid[size_t(RR) * Cols + CC]); };
		return Lerp(Lerp(F(R0, C0), F(R0, C0 + 1), FC), Lerp(F(R0 + 1, C0), F(R0 + 1, C0 + 1), FC), FR);
	}

	double FShelterMap::FactorAt(double X, double Y) const
	{
		return LeeAt(X, Y) * BuildAt(X, Y);
	}
}
