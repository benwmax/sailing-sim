"""The sim reel's Movie Render Queue executor (docs/sim-reel/), run in the game (-game) by Tools/reel/capture_reel.py.

The game sets the shot up from its own launch args (-SailingGallery, -SailingCapture, weather, boat...) and renders
through its own camera; this executor only times the render. It reads the job from -SailingReelJob=<abs path to json>
(written by capture_reel.py), waits until the game clock reaches the job's start_s (the engine runs at a fixed step
from launch, -UseFixedTimeStep -FPS=<fps>, so the world at that moment is the same every run), then builds the
pipeline in memory: frame range and rate, resolution, samples, warm-up and the image sequence it writes. Nothing here
is saved, so the job needs no config asset; the one asset is the empty /Game/Reel/LS_Reel (scripts/make_reel_sequence.py).

Launch args: -MoviePipelineLocalExecutorClass=/Script/MovieRenderPipelineCore.MoviePipelinePythonHostExecutor
-ExecutorPythonClass=/Engine/PythonTypes.SailingReelExecutor -SailingReelJob=<json>
"""
import json
import os

import unreal

SEQUENCE = "/Game/Reel/LS_Reel.LS_Reel"


@unreal.uclass()
class SailingReelExecutor(unreal.MoviePipelinePythonHostExecutor):
    pipeline = unreal.uproperty(unreal.MoviePipeline)
    reel_queue = unreal.uproperty(unreal.MoviePipelineQueue)
    job_path = unreal.uproperty(str)
    start_s = unreal.uproperty(float)
    started = unreal.uproperty(bool)
    time_at_start = unreal.uproperty(float)

    def _post_init(self):
        self.pipeline = None
        self.reel_queue = None
        self.job_path = ""
        self.start_s = 0.0
        self.started = False
        self.time_at_start = 0.0

    def _job(self):
        with open(self.job_path) as f:
            return json.load(f)

    def _done(self, ok, why=""):
        job = self._job()
        with open(os.path.join(job["output_dir"], "done.json"), "w") as f:
            json.dump({"success": bool(ok), "why": why, "game_time_at_start": self.time_at_start}, f)

    @unreal.ufunction(override=True)
    def execute_delayed(self, in_pipeline_queue):
        _, _, params = unreal.SystemLibrary.parse_command_line(unreal.SystemLibrary.get_command_line())
        self.job_path = params.get("SailingReelJob", "").strip('"')
        if not self.job_path or not os.path.isfile(self.job_path):
            unreal.log_error(f"Sim reel: no job file (-SailingReelJob={self.job_path})")
            self.on_executor_errored()
            return
        self.start_s = float(self._job().get("start_s", 0.0))
        unreal.log(f"Sim reel: job {self.job_path}, rendering from {self.start_s:.1f} s of game time")

    def _start(self):
        job = self._job()
        world = self.get_last_loaded_world()
        self.time_at_start = unreal.GameplayStatics.get_time_seconds(world)
        self.reel_queue = unreal.new_object(unreal.MoviePipelineQueue, outer=self)
        mjob = self.reel_queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
        mjob.sequence = unreal.SoftObjectPath(SEQUENCE)
        mjob.map = unreal.SoftObjectPath(world.get_path_name())
        cfg = mjob.get_configuration()

        out = cfg.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
        out.output_directory = unreal.DirectoryPath(job["output_dir"])
        out.file_name_format = "{frame_number}"
        out.zero_pad_frame_numbers = 5
        out.output_resolution = unreal.IntPoint(job["width"], job["height"])
        out.use_custom_frame_rate = True
        out.output_frame_rate = unreal.FrameRate(job["fps"], 1)
        out.use_custom_playback_range = True
        out.custom_start_frame = 0
        # The sequence plays at the world's time dilation (a time-lapse), so it reaches its end that many times sooner.
        out.custom_end_frame = round(job["frames"] * job.get("dilation", 1))
        out.override_existing_output = True

        aa = cfg.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
        aa.spatial_sample_count = job["spatial"]
        aa.temporal_sample_count = job["temporal"]
        # More than one spatial sample replaces the game's TAA (each sample is jittered and accumulated instead).
        aa.override_anti_aliasing = job["spatial"] > 1
        aa.anti_aliasing_method = unreal.AntiAliasingMethod.AAM_NONE
        aa.use_camera_cut_for_warm_up = False
        aa.engine_warm_up_count = job["engine_warmup"]
        aa.render_warm_up_count = job["render_warmup"]
        aa.render_warm_up_frames = job["render_warmup"] > 0

        # Movie Render Queue adds its game overrides with cinematic scalability by default, which would replace the
        # tier's own settings (Lumen, clouds, water): the reel shows the game's tier (-SailingQuality) instead.
        game = cfg.find_or_add_setting_by_class(unreal.MoviePipelineGameOverrideSetting)
        game.cinematic_quality_settings = False

        cfg.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
        if job.get("format") == "exr":
            cfg.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_EXR)
        else:
            cfg.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
        cfg.initialize_transient_settings()

        self.pipeline = unreal.new_object(self.target_pipeline_class, outer=world, base_type=unreal.MoviePipeline)
        self.pipeline.on_movie_pipeline_work_finished_delegate.add_function_unique(self, "on_finished")
        self.pipeline.initialize(mjob)
        self.started = True
        unreal.log(f"Sim reel: {job['frames']} frames at {job['fps']} fps, {job['width']}x{job['height']}, "
                   f"{job['spatial']} spatial x {job['temporal']} temporal samples -> {job['output_dir']}")

    @unreal.ufunction(override=True)
    def on_begin_frame(self):
        super(SailingReelExecutor, self).on_begin_frame()
        if self.started or not self.job_path:
            return
        world = self.get_last_loaded_world()
        if world and unreal.GameplayStatics.get_time_seconds(world) >= self.start_s:
            self._start()

    @unreal.ufunction(override=True)
    def is_rendering(self):
        return self.pipeline is not None

    @unreal.ufunction(ret=None, params=[unreal.MoviePipelineOutputData])
    def on_finished(self, results):
        unreal.log(f"Sim reel: render finished, success {results.success}")
        self._done(results.success)
        self.pipeline = None
        self.on_executor_finished_impl()
