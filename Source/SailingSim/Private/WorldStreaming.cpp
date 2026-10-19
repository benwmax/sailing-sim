#include "WorldStreaming.h"
#include "LakeData.h"
#include "SailingSim.h"
#include "Async/Async.h"
#include "Async/ParallelFor.h"
#include "HAL/PlatformFileManager.h"
#include "HAL/PlatformTime.h"
#include "Misc/Compression.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

FWorldStreamer::~FWorldStreamer()
{
	Stop();
}

bool FWorldStreamer::Start(FLakeData& InLake, const FString& Directory, const FString& Name)
{
	Stop();
	Lake = &InLake;
	Path = Directory / (Name + TEXT(".tiles"));
	Index = Sailing::FTileIndex();
	if (IFileHandle* File = FPlatformFileManager::Get().GetPlatformFile().OpenRead(*Path))
	{
		// The header and the entries only: the tiles are read as the boat comes near them.
		TArray<uint8> Head;
		Head.SetNumUninitialized(int32(Sailing::FTileIndex::kHeaderBytes));
		const bool bHead = File->Read(Head.GetData(), Head.Num());
		const size_t Need = bHead ? Sailing::FTileIndex::HeaderSize(Head.GetData(), Head.Num()) : 0;
		if (Need > 0)
		{
			Head.SetNumUninitialized(int32(Need));
			File->Seek(0);
			if (File->Read(Head.GetData(), Head.Num())) Index.Parse(Head.GetData(), Head.Num());
		}
		delete File;
		if (!Index.IsValid()) UE_LOG(LogSailing, Warning, TEXT("World streaming: %s is not a tile index"), *Path);
	}
	if (!Index.IsValid())
	{
		// A world baked as one grid: an index over the grid, every tile resident.
		if (!InLake.Terrain.IsValid()) { Lake = nullptr; return false; }
		Index = Sailing::FTileIndex::ForGrid(InLake.Terrain, Sailing::FTileIndex::kTileM);
	}
	const int32 N = int32(Index.GetTiles().size());
	Tiles.Reset();
	Tiles.SetNum(N);
	ResidentFlags.assign(N, Index.IsStreamed() ? 0 : 1);
	InFlightFlags.assign(N, 0);
	Resident = Index.IsStreamed() ? 0 : N;
	Bytes = 0;
	Loads = Drops = 0;
	++Generation;
	UE_LOG(LogSailing, Display, TEXT("World streaming: %s, %d tiles of %.1f km%s"), *Name, N, Index.GetTileM() / 1000.0,
		Index.IsStreamed() ? TEXT(" streamed from the .tiles file") : TEXT(" over the whole grid (resident)"));
	return true;
}

void FWorldStreamer::Stop()
{
	if (InFlight.IsValid()) InFlight.Wait();
	InFlight = TFuture<FLoaded>();
	Queue.Reset();
	std::fill(InFlightFlags.begin(), InFlightFlags.end(), 0);
}

FWorldStreamer::FLoaded FWorldStreamer::ReadTile(const FString& File, const Sailing::FTileIndex& InIndex, int32 Tile)
{
	FLoaded Out;
	Out.Tile = Tile;
	const Sailing::FTileEntry& E = InIndex.GetTiles()[Tile];
	TUniquePtr<IFileHandle> Handle(FPlatformFileManager::Get().GetPlatformFile().OpenRead(*File));
	if (!Handle || !Handle->Seek(int64(E.Offset))) return Out;
	TArray<uint8> Stored;
	Stored.SetNumUninitialized(int32(E.StoredSize));
	if (!Handle->Read(Stored.GetData(), Stored.Num())) return Out;
	const int32 RawSize = (E.Cells + 1) * (E.Cells + 1) * 2;
	if (E.Flags & Sailing::kTileZlib)
	{
		TArray<uint8> Raw;
		Raw.SetNumUninitialized(RawSize);
		if (!FCompression::UncompressMemory(NAME_Zlib, Raw.GetData(), RawSize, Stored.GetData(), Stored.Num())) return Out;
		Out.Data = InIndex.MakeTile(E, Raw.GetData(), size_t(Raw.Num()));
	}
	else
	{
		Out.Data = InIndex.MakeTile(E, Stored.GetData(), size_t(Stored.Num()));
	}
	return Out;
}

void FWorldStreamer::Install(FLoaded&& L)
{
	if (L.Tile == INDEX_NONE || !Tiles.IsValidIndex(L.Tile)) return;
	InFlightFlags[L.Tile] = 0;
	if (!L.Data)
	{
		UE_LOG(LogSailing, Warning, TEXT("World streaming: tile %d did not read"), L.Tile);
		return;
	}
	if (!ResidentFlags[L.Tile]) { ++Resident; ++Loads; }
	else Bytes -= int64(Tiles[L.Tile]->Heights.size() * 2);
	Tiles[L.Tile] = MoveTemp(L.Data);
	Bytes += int64(Tiles[L.Tile]->Heights.size() * 2);
	ResidentFlags[L.Tile] = 1;
	bDirty = true;
}

void FWorldStreamer::Drop(int32 Tile)
{
	if (!ResidentFlags[Tile]) return;
	ResidentFlags[Tile] = 0;
	if (Tiles[Tile]) Bytes -= int64(Tiles[Tile]->Heights.size() * 2);
	Tiles[Tile].reset();
	--Resident;
	++Drops;
	bDirty = true;
}

void FWorldStreamer::Publish()
{
	if (!bDirty || !Lake) return;
	bDirty = false;
	++Generation;
	std::vector<std::shared_ptr<const Sailing::FTerrainTile>> Set;
	Set.reserve(Resident);
	for (const std::shared_ptr<const Sailing::FTerrainTile>& T : Tiles) if (T) Set.push_back(T);
	Lake->Terrain.SetTiles(std::make_shared<const Sailing::FTileSet>(Index.GetTileM(), Index.GetOriginX(), Index.GetOriginY(), Set), Index.GetFinestCell());
}

void FWorldStreamer::LoadAround(double X, double Y, double RadiusM)
{
	if (!Lake || !Index.IsStreamed()) return;
	const double Start = FPlatformTime::Seconds();
	TArray<int32> Want;
	const std::vector<Sailing::FTileEntry>& Entries = Index.GetTiles();
	for (int32 K = 0; K < int32(Entries.size()); ++K)
		if (!ResidentFlags[K] && Index.DistanceTo(Entries[K], X, Y) <= RadiusM) Want.Add(K);
	TArray<FLoaded> Read;
	Read.SetNum(Want.Num());
	ParallelFor(Want.Num(), [&](int32 I) { Read[I] = ReadTile(Path, Index, Want[I]); });
	for (FLoaded& L : Read) Install(MoveTemp(L));
	Publish();
	PlannedX = PlannedY = 1e300;   // plan again from here
	UE_LOG(LogSailing, Display, TEXT("World streaming: %d tiles within %.0f km read in %.0f ms (%d resident, %.1f MB)"), Want.Num(), RadiusM / 1000.0,
		(FPlatformTime::Seconds() - Start) * 1000.0, Resident, Bytes / 1e6);
}

void FWorldStreamer::Tick(double X, double Y)
{
	if (!Lake || !Index.IsStreamed()) return;
	const double Start = FPlatformTime::Seconds();
	// What the worker finished.
	if (InFlight.IsValid() && InFlight.IsReady())
	{
		Install(InFlight.Consume());
		InFlight = TFuture<FLoaded>();
	}
	// The plan, again when the boat has moved a tenth of a tile (the boat crosses a tile in minutes).
	if (FMath::Abs(X - PlannedX) + FMath::Abs(Y - PlannedY) > 0.1 * Index.GetTileM())
	{
		PlannedX = X;
		PlannedY = Y;
		std::vector<int> Load, DropList;
		Sailing::PlanStreaming(Index, X, Y, Radii, ResidentFlags, InFlightFlags, Load, DropList);
		for (const int D : DropList) Drop(D);
		Queue.Reset();
		for (const int L : Load) Queue.Add(L);
	}
	// One read at a time on the worker, nearest first.
	if (!InFlight.IsValid())
	{
		while (Queue.Num() > 0)
		{
			const int32 Next = Queue[0];
			Queue.RemoveAt(0);
			if (ResidentFlags[Next] || InFlightFlags[Next]) continue;
			InFlightFlags[Next] = 1;
			InFlight = Async(EAsyncExecution::ThreadPool, [File = Path, Copy = Index, Next]() { return ReadTile(File, Copy, Next); });
			break;
		}
	}
	Publish();
	Last = (FPlatformTime::Seconds() - Start) * 1000.0;
	Longest = FMath::Max(Longest, Last);
}
