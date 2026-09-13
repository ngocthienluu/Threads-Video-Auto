"""Build a filter graph using numbered inputs only, never user text/paths."""
def build_filter_graph(project, timeline, music_index=None, watermark_index=None, background_audio=False, overlays=None):
    v = project.video_settings
    total = timeline.total_duration
    graph = [f"[0:v]setpts=PTS-STARTPTS,scale=iw*sar:ih,setsar=1,scale={v.width}:{v.height}:force_original_aspect_ratio=increase,crop={v.width}:{v.height},fps={v.fps},trim=duration={total:.6f}[base0]"]
    if overlays is not None:
        from app.core.editor_objects import ObjectType
        background=next(o for o in project.editor_objects if o.type==ObjectType.BACKGROUND)
        if not background.visible:
            graph=[f"color=c=black:s={v.width}x{v.height}:r={v.fps}:d={total:.6f}[base0]"]
    audio = []
    for n, segment in enumerate(timeline.segments):
        audio_index = 2 + 2*n
        duration = segment.voice_end - segment.voice_start
        delay = round(segment.voice_start * 48000)
        graph.append(f"[{audio_index}:a]atrim=duration={duration:.6f},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,adelay={delay}S:all=1[voice{n}]")
        audio.append(f"[voice{n}]")
    if overlays is None:
        # Compatibility for callers supplying legacy pre-scaled input images.
        from app.renderer.editor_compositor import RenderOverlay
        overlays=[RenderOverlay(1+2*n,"(W-w)/2",f"max(0,min(H-h,H*{v.comment_y_ratio:.6f}-h/2))",seg.start_time,seg.end_time,100)
                  for n,seg in enumerate(timeline.segments)]
        if watermark_index is not None:overlays.append(RenderOverlay(watermark_index,0,0,0,total,300))
    video="base0"
    for n,overlay in enumerate(sorted(overlays,key=lambda o:o.z_index)):
        graph.append(f"[{overlay.input_index}:v]format=rgba,setsar=1[img{n}]")
        graph.append(f"[{video}][img{n}]overlay=x='{overlay.x}':y='{overlay.y}':enable='gte(t,{overlay.start_time:.6f})*lt(t,{overlay.end_time:.6f})':eof_action=pass[base{n+1}]")
        video=f"base{n+1}"
    graph.append(f"[{video}]format=yuv420p[vout]")
    if background_audio:
        graph.append(f"[0:a]asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,volume={project.background_settings.volume:.6f},atrim=duration={total:.6f}[gameaudio]")
        audio.append("[gameaudio]")
    if music_index is not None:
        m = project.music_settings
        fade_start = max(0, total - m.fade_out)
        fades = (f",afade=t=in:d={m.fade_in:.6f}" if m.fade_in > 0 else "") + (f",afade=t=out:st={fade_start:.6f}:d={m.fade_out:.6f}" if m.fade_out > 0 else "")
        graph.append(f"[{music_index}:a]asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,volume={m.volume:.6f},apad,atrim=duration={total:.6f}{fades}[music]")
        audio.append("[music]")
    graph.append(''.join(audio) + f"amix=inputs={len(audio)}:normalize=0:duration=longest,alimiter=limit=0.95:latency=1,apad,atrim=duration={total:.6f}[aout]")
    return ";\n".join(graph)
