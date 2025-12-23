const program = window.PROGRAM || [];

const normalize = (value) =>
  (value || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

const getQueryTitle = () => {
  const params = new URLSearchParams(window.location.search);
  return params.get('title') || '';
};

const formatDateFR = (dateISO) => {
  const date = new Date(`${dateISO}T00:00:00`);
  return new Intl.DateTimeFormat('fr-FR', {
    weekday: 'long',
    day: '2-digit',
    month: 'long'
  }).format(date);
};

const groupBy = (list, keyFn) => {
  const map = new Map();
  list.forEach((item) => {
    const key = keyFn(item);
    const existing = map.get(key) || [];
    existing.push(item);
    map.set(key, existing);
  });
  return map;
};

const decodeEntities = (value) => {
  if (!value) return '';
  const textarea = document.createElement('textarea');
  textarea.innerHTML = value;
  return textarea.value;
};

const findMovie = (movies, title) => {
  const target = normalize(title);
  if (!target) return null;
  const direct = movies.find((m) => normalize(m.movie_title) === target);
  if (direct) return direct;
  return movies.find((m) => normalize(m.movie_title).includes(target) || target.includes(normalize(m.movie_title))) || null;
};

const render = async () => {
  const titleParam = getQueryTitle();
  const movieTitleEl = document.querySelector('#movieTitle');
  const movieMetaEl = document.querySelector('#movieMeta');
  const movieBlurbEl = document.querySelector('#movieBlurb');
  const movieSourceEl = document.querySelector('#movieSource');
  const movieScreeningsEl = document.querySelector('#movieScreenings');
  const movieTrailerEl = document.querySelector('#movieTrailer');
  const trailerSection = document.querySelector('#movieTrailerSection');

  if (!titleParam) {
    movieTitleEl.textContent = 'Film introuvable';
    movieMetaEl.textContent = '';
    return;
  }

  let movies = window.MOVIES || null;
  if (!movies) {
    try {
      const response = await fetch('movies.json?v=20251222a');
      movies = await response.json();
    } catch (error) {
      movieMetaEl.textContent = 'Impossible de charger les données des films.';
      return;
    }
  }
  const movie = findMovie(movies, titleParam);

  if (!movie) {
    movieTitleEl.textContent = titleParam;
    movieMetaEl.textContent = 'Film introuvable dans les données.';
    return;
  }

  movieTitleEl.textContent = movie.movie_title;

  const metaParts = [];
  if (movie.director) metaParts.push(decodeEntities(movie.director));
  if (movie.cast) metaParts.push(`Avec ${decodeEntities(movie.cast)}`);
  if (movie.genre) metaParts.push(movie.genre);
  if (movie.duration) metaParts.push(movie.duration);
  if (movie.release_date) {
    const year = String(movie.release_date).slice(0, 4);
    if (year) metaParts.push(year);
  }
  movieMetaEl.textContent = metaParts.join(' · ');

  movieBlurbEl.textContent = decodeEntities(movie.blurb) || 'Résumé indisponible.';
  if (movie.source === 'tmdb') {
    movieSourceEl.textContent = 'Résumé issu de TMDB.';
  } else if (movie.source === 'pdf') {
    movieSourceEl.textContent = 'Résumé issu du programme Sceni Qua Non.';
  } else {
    movieSourceEl.textContent = '';
  }

  const screenings = program.filter((item) => normalize(item.movie_title) === normalize(movie.movie_title));
  const grouped = Array.from(groupBy(screenings, (item) => item.date))
    .map(([dateISO, items]) => ({
      dateISO,
      items: items.sort((a, b) => a.time.localeCompare(b.time))
    }))
    .sort((a, b) => a.dateISO.localeCompare(b.dateISO));

  if (grouped.length === 0) {
    movieScreeningsEl.textContent = 'Aucune séance.';
  } else {
    grouped.forEach(({ dateISO, items }) => {
      const section = document.createElement('div');
      section.className = 'group__section';

      const header = document.createElement('div');
      header.className = 'group__section-header';

      const title = document.createElement('h3');
      title.className = 'group__section-title';
      title.textContent = formatDateFR(dateISO);

      header.appendChild(title);
      section.appendChild(header);

      items.forEach((item) => {
        const row = document.createElement('div');
        row.className = 'showtime';

        const time = document.createElement('div');
        time.className = 'showtime__time';
        time.textContent = item.time;

        const cinema = document.createElement('div');
        cinema.className = 'showtime__title';
        cinema.textContent = item.cinema;

        row.append(time, cinema);
        section.appendChild(row);
      });

      movieScreeningsEl.appendChild(section);
    });
  }

  if (movie.yt_trailer_url) {
    const url = new URL(movie.yt_trailer_url);
    const id = url.searchParams.get('v');
    if (id && window.location.protocol !== 'file:') {
      const iframe = document.createElement('iframe');
      iframe.width = '100%';
      iframe.height = '360';
      iframe.src = `https://www.youtube.com/embed/${id}`;
      iframe.title = 'Bande-annonce';
      iframe.loading = 'lazy';
      iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture';
      iframe.allowFullscreen = true;
      movieTrailerEl.appendChild(iframe);
    } else {
      const link = document.createElement('a');
      link.href = movie.yt_trailer_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = 'Voir la bande-annonce sur YouTube';
      movieTrailerEl.appendChild(link);
    }
  } else {
    trailerSection.remove();
  }
};

render();
