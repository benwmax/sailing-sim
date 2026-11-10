READ FIRST: these are NOT 4K numbers.
Main 5e8233ef, Ultra, 1920x1080 WINDOWED. The runs asked for -ResX=3840 -ResY=2160 windowed, but Bean's display is
3840x2160 at 150% Windows scaling (a 2560x1440 desktop), so a 3840x2160 window does not fit and the engine fell back to a
1920x1080 window (logs: "1920x1080 (window mode 2)"; bench.json "resolution" 1920x1080 on every run). A true 4K run
needs fullscreen; that waits on Bean.
Game not in front (bench.json "foreground" 0 on all runs but one, at 0.095). No upscaler: render_pct 100 on every run.
1% low = 1000 / p99_ms. gpu = gpu.total_ms where present (Development), else gpu_frame_ms (Shipping).
Development vs Shipping: the Development package (B) spends about 12-14.5 ms on the game thread against about 9 ms in
Shipping (A). That is Development's checks and stats, not the GPU (GPU 6-10 ms in both). B and A are different views too
(B: the 16 bench-visual scenes, 12 s each, demo autopilot; A: the Lake launch spots 0-4, 60 s each).
Bottleneck: the render thread in both (render_th about 17-25 ms in B, about 11-12 ms in A, against GPU 6-10 ms).
