export default function AppBackgroundVideo() {
  return (
    <div className="app-bg-video-wrap" aria-hidden="true">
      <video
        className="app-bg-video"
        src="https://framerusercontent.com/assets/XyQKBChh8CZBaaXrJoxPbwvI.mp4"
        loop
        muted
        playsInline
        autoPlay
        preload="auto"
      />
      <div className="app-bg-video-overlay" />
    </div>
  );
}
