def test_flat_playlist_args_can_start_at_an_offset():
    from youmudow.adapters.ytdlp_adapter import YtdlpConfig
    from youmudow.adapters.ytdlp_args import build_flat_playlist_args

    args = build_flat_playlist_args(YtdlpConfig(), "https://x.test/list", playlist_end=50)
    assert "--playlist-start" not in args
    offset = build_flat_playlist_args(
        YtdlpConfig(), "https://x.test/list", playlist_end=50, playlist_start=51
    )
    assert offset[offset.index("--playlist-start") + 1] == "51"
