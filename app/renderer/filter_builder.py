"""Build a filter graph using numbered inputs only, never user text/paths."""
def build_filter_graph(project, timeline, music_index=None, watermark_index=None, background_audio=False):
    v = project.video_settings
    total = timeline.total_duration
    graph = [f"[0:v]setpts=PTS-STARTPTS,scale=iw*sar:ih,setsar=1,scale={v.width}:{v.height}:force_original_aspect_ratio=increase,crop={v.width}:{v.height},fps={v.fps},trim=duration={total:.6f}[base0]"]
    audio = []
    for n, segment in enumerate(timeline.segments):
        image_index, audio_index = 1 + 2*n, 2 + 2*n
        graph.append(f"[{image_index}:v]format=rgba,setsar=1[img{n}]")
        y = f"max(0,min(H-h,H*{v.comment_y_ratio:.6f}-h/2))"
        graph.append(f"[base{n}][img{n}]overlay=x=(W-w)/2:y='{y}':enable='gte(t,{segment.start_time:.6f})*lt(t,{segment.end_time:.6f})':eof_action=pass[base{n+1}]")
        duration = segment.voice_end - segment.voice_start
        delay = round(segment.voice_start * 48000)
        graph.append(f"[{audio_index}:a]atrim=duration={duration:.6f},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,adelay={delay}S:all=1[voice{n}]")
        audio.append(f"[voice{n}]")
    video = f"base{len(timeline.segments)}"
    if watermark_index is not None:
        graph.append(f"[{video}][{watermark_index}:v]overlay=0:0:eof_action=repeat[marked]")
        video = "marked"
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
