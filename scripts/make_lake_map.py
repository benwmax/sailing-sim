"""Builds /Game/Maps/Lake: flat water, sky, sun, a player start and the sailing game mode.

Run with scripts/make-map.sh. The map is generated so it can be rebuilt from code;
the boat itself is spawned at the player start by ASailingGameMode.
"""
import unreal

MAP_PATH = "/Game/Maps/Lake"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if unreal.EditorAssetLibrary.does_asset_exist(MAP_PATH):
    unreal.EditorAssetLibrary.delete_asset(MAP_PATH)

if not level_subsystem.new_level(MAP_PATH):
    raise RuntimeError("Could not create " + MAP_PATH)


def spawn(cls, location=(0, 0, 0), rotation=(0, 0, 0), label=None):
    actor = actor_subsystem.spawn_actor_from_class(
        cls, unreal.Vector(*location), unreal.Rotator(roll=rotation[2], pitch=rotation[0], yaw=rotation[1]))
    if label:
        actor.set_actor_label(label)
    return actor


water = spawn(unreal.load_class(None, "/Script/SailingSim.FlatWater"), label="Water")

# Afternoon sun from the southwest, typical of a Texas summer sea breeze day.
sun = spawn(unreal.DirectionalLight, (0, 0, 1000), (-35, 225, 0), "Sun")
sun_light = sun.get_component_by_class(unreal.DirectionalLightComponent)
sun_light.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
sun_light.set_editor_property("atmosphere_sun_light", True)
sun_light.set_editor_property("intensity", 10.0)

spawn(unreal.SkyAtmosphere, label="SkyAtmosphere")

sky = spawn(unreal.SkyLight, (0, 0, 500), label="SkyLight")
sky_light = sky.get_component_by_class(unreal.SkyLightComponent)
sky_light.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
sky_light.set_editor_property("real_time_capture", True)

fog = spawn(unreal.ExponentialHeightFog, (0, 0, 0), label="HeightFog")
fog_component = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
fog_component.set_editor_property("fog_density", 0.005)

spawn(unreal.PlayerStart, (0, 0, 100), (0, 0, 0), "PlayerStart")

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
settings = world.get_world_settings()
settings.set_editor_property("default_game_mode", unreal.load_class(None, "/Script/SailingSim.SailingGameMode"))

if not level_subsystem.save_current_level():
    raise RuntimeError("Could not save " + MAP_PATH)
unreal.log("Lake map saved to " + MAP_PATH)
