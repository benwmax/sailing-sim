#include "FarRing.h"
#include "BenchRunner.h"
#include "LakeData.h"
#include "WorldKit.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/Parse.h"
#include "Async/Async.h"
#include "Engine/StaticMesh.h"
#include "HAL/PlatformTime.h"
#include "UObject/Package.h"
#include "UObject/UObjectGlobals.h"

namespace
{
	template <typename T> T ReadAt(const TArray<uint8>& B, int64 At)
	{
		T V;
		FMemory::Memcpy(&V, B.GetData() + At, sizeof(T));
		return V;
	}
	constexpr int64 kHeaderBytes = 4 + 4 + 4 + 4 * 4;
	constexpr int64 kIndexBytes = 16;
}

FString FFarRingData::PathFor(const FString& World)
{
	return FPaths::Combine(FLakeData::DefaultDirectory(), World + TEXT(".far"));
}

bool FFarRingData::Load(const FString& Path, bool bHeights)
{
	Tiles.Reset();
	ByCell.Reset();
	Bytes.Reset();
	TArray<uint8> B;
	if (!FFileHelper::LoadFileToArray(B, *Path, FILEREAD_Silent) || B.Num() < kHeaderBytes || FMemory::Memcmp(B.GetData(), "SSFR", 4) != 0) return false;
	if (ReadAt<uint32>(B, 4) != 1) return false;
	const int32 Count = int32(ReadAt<uint32>(B, 8));
	TileM = ReadAt<float>(B, 12);
	InnerM = ReadAt<float>(B, 16);
	OuterM = ReadAt<float>(B, 20);
	Unit = ReadAt<float>(B, 24);
	if (Count <= 0 || B.Num() < kHeaderBytes + Count * kIndexBytes || TileM <= 0.0 || Unit <= 0.0) return false;
	for (int32 K = 0; K < Count; ++K)
	{
		const int64 At = kHeaderBytes + K * kIndexBytes;
		FFarRingTile T;
		T.Row = ReadAt<int32>(B, At);
		T.Col = ReadAt<int32>(B, At + 4);
		T.Cells = int32(ReadAt<uint32>(B, At + 8));
		T.Offset = int32(ReadAt<uint32>(B, At + 12));
		const int64 Nodes = int64(T.Cells + 1) * (T.Cells + 1);
		if (T.Cells < 2 || T.Offset + Nodes * 3 > B.Num()) { Tiles.Reset(); return false; }
		ByCell.Add(FIntPoint(T.Row, T.Col), Tiles.Add(T));
	}
	if (bHeights) Bytes = MoveTemp(B);
	return true;
}

int32 FFarRingData::FindTile(int32 Row, int32 Col) const
{
	const int32* I = ByCell.Find(FIntPoint(Row, Col));
	return I ? *I : INDEX_NONE;
}

double FFarRingData::NodeHeight(int32 Tile, int32 R, int32 C) const
{
	const FFarRingTile& T = Tiles[Tile];
	R = FMath::Clamp(R, 0, T.Cells);
	C = FMath::Clamp(C, 0, T.Cells);
	return ReadAt<int16>(Bytes, T.Offset + 2 * (int64(R) * (T.Cells + 1) + C)) * Unit;
}

double FFarRingData::NodeSky(int32 Tile, int32 R, int32 C) const
{
	const FFarRingTile& T = Tiles[Tile];
	const int64 Nodes = int64(T.Cells + 1) * (T.Cells + 1);
	R = FMath::Clamp(R, 0, T.Cells);
	C = FMath::Clamp(C, 0, T.Cells);
	return Bytes[T.Offset + 2 * Nodes + int64(R) * (T.Cells + 1) + C] / 255.0;
}

bool FFarRingData::HeightAt(double X, double Y, double& Out) const
{
	if (Bytes.Num() == 0) return false;
	const int32 Row = FMath::FloorToInt32(X / TileM), Col = FMath::FloorToInt32(Y / TileM);
	const int32 I = FindTile(Row, Col);
	if (I == INDEX_NONE) return false;
	const FFarRingTile& T = Tiles[I];
	const double Step = TileM / T.Cells;
	const double R = (X - Row * TileM) / Step, C = (Y - Col * TileM) / Step;
	const int32 R0 = FMath::Clamp(FMath::FloorToInt32(R), 0, T.Cells - 1), C0 = FMath::Clamp(FMath::FloorToInt32(C), 0, T.Cells - 1);
	const double FR = R - R0, FC = C - C0;
	// The bake's two triangles per cell: (R0,C0) (R0,C0+1) (R0+1,C0), then (R0,C0+1) (R0+1,C0+1) (R0+1,C0).
	const double H00 = NodeHeight(I, R0, C0), H01 = NodeHeight(I, R0, C0 + 1), H10 = NodeHeight(I, R0 + 1, C0), H11 = NodeHeight(I, R0 + 1, C0 + 1);
	Out = FR + FC <= 1.0 ? H00 + FC * (H01 - H00) + FR * (H10 - H00) : H11 + (1.0 - FC) * (H10 - H11) + (1.0 - FR) * (H01 - H11);
	return true;
}

FString FFarRingData::AssetPath(const FString& World, const FFarRingTile& T)
{
	const FString Name = FKitGeometry::TileAssetName(TEXT("Far_") + World, FIntPoint(T.Row, T.Col));
	return FString::Printf(TEXT("/Game/World/Far/%s.%s"), *Name, *Name);
}

namespace FarRing
{
	double OffsetZ(double DistanceM, double Z, double InnerM, double BandEndM)
	{
		const double Drop = CurvatureDrop(DistanceM);
		if (DistanceM < InnerM - SinkMarginM) return -Drop - FMath::Max(Z - BuryZ, 0.0);
		const double T = FMath::Clamp((DistanceM - BandEndM) / RiseM, 0.0, 1.0);
		return -Drop - UnderM * (1.0 - T * T * (3.0 - 2.0 * T));
	}

	bool TileVisible(const FFarRingData& Ring, const FFarRingTile& Tile, const FVector2D& Cam)
	{
		const FVector2D Lo = Ring.TileOrigin(Tile), Hi = Lo + FVector2D(Ring.TileM, Ring.TileM);
		const double DX = FMath::Max3(Lo.X - Cam.X, 0.0, Cam.X - Hi.X), DY = FMath::Max3(Lo.Y - Cam.Y, 0.0, Cam.Y - Hi.Y);
		const double Nearest = FMath::Sqrt(DX * DX + DY * DY);
		const double FX = FMath::Max(FMath::Abs(Cam.X - Lo.X), FMath::Abs(Cam.X - Hi.X)), FY = FMath::Max(FMath::Abs(Cam.Y - Lo.Y), FMath::Abs(Cam.Y - Hi.Y));
		const double Farthest = FMath::Sqrt(FX * FX + FY * FY);
		return Farthest > Ring.InnerM - SinkMarginM && Nearest < Ring.OuterM;
	}

	bool Enabled()
	{
		static SailingArgs::FCachedFlag NoRing(TEXT("SailingNoFarRing"));
		return !NoRing.Get();
	}
}

void FFarRingLoader::Note(double StartSeconds)
{
	Longest = FMath::Max(Longest, (FPlatformTime::Seconds() - StartSeconds) * 1000.0);
}

void FFarRingLoader::Reset()
{
	if (Index.IsValid()) Index.Wait();
	Index = {};
	Ring.Reset();
	State.Reset();
	Requested = 0;
	Longest = 0.0;
}

bool FFarRingLoader::Start(const FString& InWorld)
{
	const double T0 = FPlatformTime::Seconds();
	Reset();
	World = InWorld;
	const FString Path = FFarRingData::PathFor(World);
	if (!FarRing::Enabled() || !FPaths::FileExists(Path)) return false;
	State = MakeShared<FState>();
	Index = Async(EAsyncExecution::ThreadPool, [Path]()
	{
		TSharedPtr<FFarRingData> D = MakeShared<FFarRingData>();
		D->Load(Path, false);
		return D;
	});
	Note(T0);
	return true;
}

void FFarRingLoader::Poll()
{
	if (Ring.IsValid() || !Index.IsValid() || !Index.IsReady()) return;
	const double T0 = FPlatformTime::Seconds();
	Ring = Index.Get();
	Index = {};
	if (Ring->IsValid())
	{
		for (int32 K = 0; K < Ring->Tiles.Num(); ++K)
		{
			const FString Package = FPackageName::ObjectPathToPackageName(FFarRingData::AssetPath(World, Ring->Tiles[K]));
			// The callback runs on the game thread when the package is in; it only notes the mesh (the State outlives this).
			TSharedPtr<FState> S = State;
			LoadPackageAsync(Package, FLoadPackageAsyncDelegate::CreateLambda([S, K](const FName&, UPackage* Loaded, EAsyncLoadingResult::Type Result)
			{
				++S->Answered;
				UStaticMesh* Mesh = Loaded && Result == EAsyncLoadingResult::Succeeded ? FindObject<UStaticMesh>(Loaded, *FPackageName::GetShortName(Loaded)) : nullptr;
				if (Mesh) { ++S->Loaded; S->Arrived.Emplace(K, TStrongObjectPtr<UStaticMesh>(Mesh)); }
				else ++S->Failed;
			}));
			++Requested;
		}
	}
	Note(T0);
}

void FFarRingLoader::TakeArrived(TArray<TPair<int32, UStaticMesh*>>& Out)
{
	if (!State.IsValid()) return;
	for (const TPair<int32, TStrongObjectPtr<UStaticMesh>>& A : State->Arrived) Out.Emplace(A.Key, A.Value.Get());
	State->Arrived.Reset();
}

bool FFarRingLoader::IsDone() const
{
	return Ring.IsValid() && (!Ring->IsValid() || (State.IsValid() && State->Answered >= Requested));
}

int32 FFarRingLoader::NumArrived() const { return State.IsValid() ? State->Loaded : 0; }
int32 FFarRingLoader::NumFailed() const { return State.IsValid() ? State->Failed : 0; }
