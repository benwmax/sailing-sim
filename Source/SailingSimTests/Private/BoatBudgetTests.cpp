#include "Misc/AutomationTest.h"
#include "Engine/StaticMesh.h"

namespace
{
	constexpr EAutomationTestFlags BoatBudgetFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter;
	// Phase 0's budgets (docs/boat-fidelity-0): a non-Nanite boat part within 40,000 triangles; at most 8 material slots per
	// mesh (each slot is a draw and a shading bin). Since the slot-merge pass (pc/boat-slots, docs/boat-slots: packs of one
	// parent's slots, BoatPacks.h) every boat meets the 8, which is now enforced; each mesh is also held at its packed count
	// as a ratchet, so no boat grows back. Lower an entry as a boat drops.
	constexpr int32 NonNaniteMaxTris = 40000;
	constexpr int32 SlotTarget = 8;
	struct FBudget { const TCHAR* Path; int32 MaxSlots; };
	const FBudget Budgets[] = {
		{ TEXT("/Game/Boats/J22Hero/SM_J22H_Hull"), 5 }, { TEXT("/Game/Boats/J22Hero/SM_J22H_Rudder"), 3 },
		{ TEXT("/Game/Boats/J22Hero/SM_J22H_Boom"), 2 }, { TEXT("/Game/Boats/J22Hero/SM_J22H_Mast"), 3 },
		{ TEXT("/Game/Boats/J22Hero/SM_J22H_Interior"), 1 }, { TEXT("/Game/Boats/J22Hero/SM_J22H_Glass"), 3 },
		{ TEXT("/Game/Boats/J22/SM_J22_Hull"), 3 }, { TEXT("/Game/Boats/J22/SM_J22_Rudder"), 2 },
		{ TEXT("/Game/Boats/J22/SM_J22_Boom"), 1 }, { TEXT("/Game/Boats/J22/SM_J22_Mast"), 2 },
		{ TEXT("/Game/Boats/J22/SM_J22_Berthed"), 3 }, { TEXT("/Game/Boats/J22/SM_J22_Berthed_1"), 3 }, { TEXT("/Game/Boats/J22/SM_J22_Berthed_2"), 3 },
		{ TEXT("/Game/Boats/J22/SM_J22_Berthed_3"), 2 }, { TEXT("/Game/Boats/J22/SM_J22_Berthed_4"), 3 }, { TEXT("/Game/Boats/J22/SM_J22_Berthed_5"), 3 },
		{ TEXT("/Game/Boats/Sunfish/SM_Sunfish_Hull"), 3 }, { TEXT("/Game/Boats/ILCA7/SM_ILCA7_Hull"), 3 },
		{ TEXT("/Game/Boats/Catalina22/SM_Catalina22_Hull"), 3 }, { TEXT("/Game/Boats/Catalina22/SM_Catalina22_Berthed"), 3 },
		{ TEXT("/Game/Boats/Catalina30/SM_Catalina30_Hull"), 4 }, { TEXT("/Game/Boats/Catalina30/SM_Catalina30_Berthed"), 3 },
		{ TEXT("/Game/Boats/Hobie16/SM_Hobie16_Hull"), 3 }, { TEXT("/Game/Boats/Corsair880/SM_Corsair880_Hull"), 3 },
		{ TEXT("/Game/Boats/Lagoon42/SM_Lagoon42_Hull"), 4 }, { TEXT("/Game/Boats/Maxi/SM_Maxi_Hull"), 3 },
		{ TEXT("/Game/Boats/Maxi/SM_Maxi_Rudder"), 1 }, { TEXT("/Game/Boats/Maxi/SM_Maxi_Boom"), 1 }, { TEXT("/Game/Boats/Maxi/SM_Maxi_Mast"), 1 },
		{ TEXT("/Game/Boats/Sunfish/SM_Sunfish_Rudder"), 2 }, { TEXT("/Game/Boats/Sunfish/SM_Sunfish_Boom"), 1 }, { TEXT("/Game/Boats/Sunfish/SM_Sunfish_Mast"), 2 },
		{ TEXT("/Game/Boats/ILCA7/SM_ILCA7_Rudder"), 2 }, { TEXT("/Game/Boats/ILCA7/SM_ILCA7_Boom"), 2 }, { TEXT("/Game/Boats/ILCA7/SM_ILCA7_Mast"), 2 },
		{ TEXT("/Game/Boats/Catalina22/SM_Catalina22_Rudder"), 2 }, { TEXT("/Game/Boats/Catalina22/SM_Catalina22_Boom"), 1 }, { TEXT("/Game/Boats/Catalina22/SM_Catalina22_Mast"), 2 },
		{ TEXT("/Game/Boats/Catalina30/SM_Catalina30_Rudder"), 1 }, { TEXT("/Game/Boats/Catalina30/SM_Catalina30_Boom"), 1 }, { TEXT("/Game/Boats/Catalina30/SM_Catalina30_Mast"), 2 },
		{ TEXT("/Game/Boats/Hobie16/SM_Hobie16_Rudder"), 2 }, { TEXT("/Game/Boats/Hobie16/SM_Hobie16_Boom"), 1 }, { TEXT("/Game/Boats/Hobie16/SM_Hobie16_Mast"), 2 },
		{ TEXT("/Game/Boats/Corsair880/SM_Corsair880_Rudder"), 2 }, { TEXT("/Game/Boats/Corsair880/SM_Corsair880_Boom"), 1 }, { TEXT("/Game/Boats/Corsair880/SM_Corsair880_Mast"), 2 },
		{ TEXT("/Game/Boats/Lagoon42/SM_Lagoon42_Rudder"), 1 }, { TEXT("/Game/Boats/Lagoon42/SM_Lagoon42_Boom"), 1 }, { TEXT("/Game/Boats/Lagoon42/SM_Lagoon42_Mast"), 2 },
		{ TEXT("/Game/Boats/Catalina22/SM_Catalina22_Berthed_1"), 3 }, { TEXT("/Game/Boats/Catalina22/SM_Catalina22_Berthed_2"), 3 }, { TEXT("/Game/Boats/Catalina22/SM_Catalina22_Berthed_3"), 3 }, { TEXT("/Game/Boats/Catalina22/SM_Catalina22_Berthed_4"), 3 }, { TEXT("/Game/Boats/Catalina22/SM_Catalina22_Berthed_5"), 3 },
		{ TEXT("/Game/Boats/Catalina30/SM_Catalina30_Berthed_1"), 3 }, { TEXT("/Game/Boats/Catalina30/SM_Catalina30_Berthed_2"), 3 }, { TEXT("/Game/Boats/Catalina30/SM_Catalina30_Berthed_3"), 3 }, { TEXT("/Game/Boats/Catalina30/SM_Catalina30_Berthed_4"), 3 }, { TEXT("/Game/Boats/Catalina30/SM_Catalina30_Berthed_5"), 3 },
	};
}

// Boat fidelity: every boat mesh within phase 0's budgets: the 8-slot target, its own packed count, the triangles.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FVisualBoatBudgetTest, "SailingSim.Visual.BoatBudget", BoatBudgetFlags)
bool FVisualBoatBudgetTest::RunTest(const FString& Parameters)
{
	int32 AtTarget = 0;
	for (const FBudget& B : Budgets)
	{
		const UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, B.Path);
		if (!TestNotNull(FString::Printf(TEXT("%s is in the project"), B.Path), Mesh)) continue;
		const int32 Slots = Mesh->GetStaticMaterials().Num();
		TestTrue(FString::Printf(TEXT("%s: %d material slots, at most %d (target %d)"), B.Path, Slots, B.MaxSlots, SlotTarget), Slots <= FMath::Min(B.MaxSlots, SlotTarget));
		if (Slots <= SlotTarget) ++AtTarget;
		if (!Mesh->IsNaniteEnabled())
		{
			const int32 Tris = Mesh->GetNumTriangles(0);
			TestTrue(FString::Printf(TEXT("%s: %d triangles (not Nanite), at most %d"), B.Path, Tris, NonNaniteMaxTris), Tris <= NonNaniteMaxTris);
		}
	}
	AddInfo(FString::Printf(TEXT("%d of %d boat meshes at or under the %d-slot target"), AtTarget, int32(UE_ARRAY_COUNT(Budgets)), SlotTarget));
	return true;
}
