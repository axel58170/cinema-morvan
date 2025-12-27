const getValidatedTrailerUrl = (rawUrl) => {
  if (!rawUrl) return null;
  try {
    const url = new URL(rawUrl);
    const allowedHosts = new Set(['www.youtube.com', 'youtu.be']);
    if (url.protocol !== 'https:' || !allowedHosts.has(url.hostname)) {
      return null;
    }
    if (url.hostname === 'www.youtube.com' && url.pathname !== '/watch') {
      return null;
    }
    if (url.hostname === 'youtu.be' && (!url.pathname || url.pathname === '/')) {
      return null;
    }
    return url;
  } catch (error) {
    return null;
  }
};

const getYouTubeVideoId = (url) => {
  if (!url) return null;
  if (url.hostname === 'www.youtube.com') {
    return url.searchParams.get('v');
  }
  if (url.hostname === 'youtu.be') {
    const id = url.pathname.slice(1);
    return id || null;
  }
  return null;
};
