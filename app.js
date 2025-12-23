const program = window.PROGRAM || [];
const moviesCatalog = window.MOVIES || [];
const state = {
  mode: 'cinema',
  movieFilter: 'all',
  versionFilters: {
    vf: true,
    vost: true,
    vof: true
  },
  cinemaFilters: new Set(),
  showAllDates: false,
  expandedCinemas: new Set(),
  expandedMovies: new Set(),
  hiddenMovies: new Set()
};

const parseTimeToMinutes = (timeRaw) => {
  if (!timeRaw) return 0;
  const match = timeRaw.match(/(\d{1,2})h(\d{2})?/i);
  if (!match) return 0;
  const hours = Number(match[1]);
  const minutes = match[2] ? Number(match[2]) : 0;
  return hours * 60 + minutes;
};

const formatDateFR = (dateISO) => {
  const date = new Date(`${dateISO}T00:00:00`);
  return new Intl.DateTimeFormat('fr-FR', {
    weekday: 'long',
    day: '2-digit',
    month: 'long'
  }).format(date);
};

const formatWeekdayFR = (dateISO) => {
  const date = new Date(`${dateISO}T00:00:00`);
  return new Intl.DateTimeFormat('fr-FR', {
    weekday: 'long'
  }).format(date);
};

const formatDateNoWeekdayFR = (dateISO) => {
  const date = new Date(`${dateISO}T00:00:00`);
  return new Intl.DateTimeFormat('fr-FR', {
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

const normalize = (value) =>
  (value || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

const moviesByTitle = new Map(
  moviesCatalog.map((movie) => [normalize(movie.movie_title), movie])
);

const decodeEntities = (value) => {
  if (!value) return '';
  const textarea = document.createElement('textarea');
  textarea.innerHTML = value;
  return textarea.value;
};

const DEFAULT_POSTER =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="160" height="240" viewBox="0 0 160 240">` +
      `<rect width="160" height="240" fill="#efe7dc"/>` +
      `<text x="50%" y="50%" fill="#a79a8b" font-size="14" font-family="Alegreya Sans, sans-serif" text-anchor="middle">Film</text>` +
    `</svg>`
  );

const setPosterImage = (img, movieData) => {
  const poster342 = movieData?.poster_url;
  const poster780 = movieData?.poster_url_w780;
  const backdrop = movieData?.backdrop_url;
  const fallback = poster342 || backdrop || DEFAULT_POSTER;
  img.src = fallback;
  if (poster342 && poster780) {
    img.srcset = `${poster342} 342w, ${poster780} 780w`;
    img.sizes = '(max-width: 700px) 100vw, 256px';
  } else {
    img.removeAttribute('srcset');
    img.removeAttribute('sizes');
  }
};
const getTodayISO = () => {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

const records = program.map((item) => ({
  ...item,
  dateISO: item.date,
  timeRaw: item.time,
  timeMinutes: parseTimeToMinutes(item.time),
  movieKey: item.movie_title,
  cinemaKey: item.cinema
}));

let allCinemas = [];

const resultsEl = document.querySelector('#results');
const movieFilterEl = document.querySelector('#movieFilter');
const vfFilterEl = document.querySelector('#vfFilter');
const vostFilterEl = document.querySelector('#vostFilter');
const vofFilterEl = document.querySelector('#vofFilter');
const cinemaFiltersEl = document.querySelector('#cinemaFilters');
const cinemaFilterWrapEl = document.querySelector('#cinemaFilterWrap');
const versionDropdownButton = document.querySelector('#versionDropdownButton');
const versionDropdownPanel = document.querySelector('#versionDropdownPanel');
const cinemaDropdownButton = document.querySelector('#cinemaDropdownButton');
const cinemaDropdownPanel = document.querySelector('#cinemaDropdownPanel');
const lastUpdatedEl = document.querySelector('#lastUpdated');
const showAllDatesEl = document.querySelector('#showAllDates');

const buildMovieOptions = () => {
  const todayISO = getTodayISO();
  const movies = Array.from(
    new Set(
      records
        .filter((item) => item.dateISO >= todayISO)
        .map((item) => item.movie_title)
    )
  ).sort((a, b) => a.localeCompare(b, 'fr'));

  movies.forEach((movie) => {
    const option = document.createElement('option');
    option.value = movie;
    option.textContent = movie;
    movieFilterEl.appendChild(option);
  });
};

const buildCinemaOptions = () => {
  const cinemas = Array.from(
    new Set(records.map((item) => item.cinema))
  ).sort((a, b) => a.localeCompare(b, 'fr'));

  allCinemas = cinemas;

  cinemas.forEach((cinema) => {
    const label = document.createElement('label');
    label.className = 'checkbox';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.value = cinema;
    input.checked = true;
    state.cinemaFilters.add(cinema);
    input.addEventListener('change', (event) => {
      const value = event.target.value;
      if (event.target.checked) {
        state.cinemaFilters.add(value);
      } else {
        state.cinemaFilters.delete(value);
      }
      updateCinemaSummary();
      render();
    });

    const span = document.createElement('span');
    span.textContent = formatCinemaName(cinema);
    label.append(input, span);
    cinemaFiltersEl.appendChild(label);
  });
};

const formatCinemaName = (name) => {
  if (!name) return '';
  const city = name.split('–')[0].trim();
  const lower = city.toLocaleLowerCase('fr');
  let titled = lower.replace(/(^|[\\s-])([\\p{L}])/gu, (match, sep, chr) => `${sep}${chr.toLocaleUpperCase('fr')}`);
  titled = titled.replace(/\\b(En|Les|La|Le|De|Du|Des)\\b/g, (match) => match.toLocaleLowerCase('fr'));
  return titled;
};

const updateVersionSummary = () => {
  if (!versionDropdownButton) return;
  const versions = [
    { key: 'vf', label: 'VF', checked: state.versionFilters.vf },
    { key: 'vost', label: 'VOST', checked: state.versionFilters.vost },
    { key: 'vof', label: 'VOF', checked: state.versionFilters.vof }
  ];
  const active = versions.filter((item) => item.checked);
  let text = 'Toutes les versions';
  if (active.length === 0) {
    text = 'Aucune version';
  } else if (active.length < versions.length) {
    text = active.map((item) => item.label).join(', ');
  }
  versionDropdownButton.textContent = text;
};

const updateCinemaSummary = () => {
  if (!cinemaDropdownButton) return;
  const selected = Array.from(state.cinemaFilters);
  let text = 'Tous les cinémas';
  if (selected.length === 0) {
    text = 'Aucun cinéma';
  } else if (selected.length < allCinemas.length) {
    if (selected.length <= 2) {
      text = selected.map((cinema) => formatCinemaName(cinema)).join(', ');
    } else {
      text = `${selected.length} cinémas`;
    }
  }
  cinemaDropdownButton.textContent = text;
};

const closeDropdowns = () => {
  document.querySelectorAll('.dropdown.is-open').forEach((dropdown) => {
    dropdown.classList.remove('is-open');
    const button = dropdown.querySelector('.dropdown__button');
    if (button) button.setAttribute('aria-expanded', 'false');
  });
};

const toggleDropdown = (button, panel) => {
  const dropdown = button?.closest('.dropdown');
  if (!dropdown) return;
  const isOpen = dropdown.classList.contains('is-open');
  closeDropdowns();
  dropdown.classList.toggle('is-open', !isOpen);
  button.setAttribute('aria-expanded', String(!isOpen));
  if (!isOpen) {
    panel?.querySelector('input')?.focus();
  }
};

const buildShowtimeRow = (item, options = {}) => {
  const row = document.createElement('div');
  row.className = 'showtime';

  const cells = [];

  const time = document.createElement('div');
  time.className = 'showtime__time';
  time.textContent = item.timeRaw;
  cells.push(time);

  if (!options.omitCinema) {
    const cinema = document.createElement('div');
    cinema.textContent = formatCinemaName(item.cinema);
    cells.push(cinema);
  }

  if (!options.omitMovie) {
    const movie = document.createElement('div');
    movie.className = 'showtime__title';
    if (item.version) {
      const link = document.createElement('a');
      link.className = 'showtime__movie-link';
      link.href = `movie.html?title=${encodeURIComponent(item.movie_title)}`;
      link.textContent = item.movie_title;
      const version = document.createElement('span');
      version.className = 'showtime__version-inline';
      version.textContent = item.version;
      movie.append(link, document.createTextNode(' '), version);
    } else {
      const link = document.createElement('a');
      link.className = 'showtime__movie-link';
      link.href = `movie.html?title=${encodeURIComponent(item.movie_title)}`;
      link.textContent = item.movie_title;
      movie.appendChild(link);
    }
    cells.push(movie);
  }

  if (options.showWeekday) {
    const weekday = document.createElement('div');
    weekday.textContent = formatWeekdayFR(item.dateISO);
    cells.push(weekday);
  }

  if (!options.omitDate) {
    const date = document.createElement('div');
    date.textContent = options.showWeekday ? formatDateNoWeekdayFR(item.dateISO) : formatDateFR(item.dateISO);
    cells.push(date);
  }

  row.append(...cells);
  return row;
};

const renderGroups = (groups, options = {}) => {
  resultsEl.innerHTML = '';

  if (groups.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'Aucune séance ne correspond à votre recherche.';
    resultsEl.appendChild(empty);
    return;
  }

  groups.forEach(({ title, items, meta, showCopy }) => {
    const container = document.createElement('article');
    container.className = 'group';
    if (options.collapsibleKey) {
      container.dataset.collapsible = options.collapsibleKey;
      container.dataset.groupKey = title;
    }

    const header = document.createElement('div');
    header.className = 'group__header';
    if (options.collapsibleKey) {
      header.setAttribute('role', 'button');
      header.setAttribute('tabindex', '0');
      const isExpanded = options.isExpanded ? options.isExpanded(title) : false;
      header.setAttribute('aria-expanded', String(isExpanded));
      container.classList.toggle('is-collapsed', !isExpanded);
    }

    const content = document.createElement('div');
    content.className = 'group__content';

    const titleEl = document.createElement('h2');
    titleEl.className = 'group__title';
    const titleLink = document.createElement('a');
    titleLink.className = 'group__title-link';
    titleLink.href = `movie.html?title=${encodeURIComponent(title)}`;
    titleLink.textContent = title;
    titleEl.appendChild(titleLink);
    content.appendChild(titleEl);

    let media = null;
    if (options.collapsibleKey === 'film') {
      container.dataset.layout = 'film';
      const movieData = moviesByTitle.get(normalize(title));
      if (movieData) {
        media = document.createElement('div');
        media.className = 'group__media';
        const img = document.createElement('img');
        img.className = 'group__poster';
        img.alt = movieData?.movie_title ? `Affiche de ${movieData.movie_title}` : 'Affiche du film';
        setPosterImage(img, movieData);
        media.appendChild(img);
      }
      if (movieData) {
        if (movieData.blurb) {
          const blurb = document.createElement('p');
          blurb.className = 'group__film-blurb';
          blurb.textContent = decodeEntities(movieData.blurb);
          content.appendChild(blurb);
        }

        const meta = document.createElement('p');
        meta.className = 'group__film-meta';
        const metaParts = [];
        if (movieData.director) metaParts.push(decodeEntities(movieData.director));
        if (movieData.cast) metaParts.push(`Avec ${decodeEntities(movieData.cast)}`);
        if (movieData.release_date) {
          const year = String(movieData.release_date).slice(0, 4);
          if (year) metaParts.push(year);
        }
        meta.textContent = metaParts.join(' · ');
        if (meta.textContent) {
          content.appendChild(meta);
        }
      }
    }

    const metaEl = document.createElement('div');
    metaEl.className = 'group__meta';
    metaEl.textContent = meta;

    if (options.collapsibleKey === 'film') {
      if (metaEl.textContent) {
        content.appendChild(metaEl);
      }

      const headRow = document.createElement('div');
      headRow.className = 'group__head-row';
      headRow.append(content);
      if (media) headRow.append(media);

      const metaRow = document.createElement('div');
      metaRow.className = 'group__head-meta';
      metaRow.textContent = metaEl.textContent;
      if (metaRow.textContent) {
        header.append(headRow, metaRow);
      } else {
        header.append(headRow);
      }
    } else {
      header.append(content, metaEl);
    }

    const body = document.createElement('div');
    body.className = 'group__body';
    if (options.collapsibleKey) {
      const isExpanded = options.isExpanded ? options.isExpanded(title) : false;
      body.hidden = !isExpanded;
    }

    const list = document.createElement('div');
    list.className = 'showtimes';
    items.forEach((item) => list.appendChild(buildShowtimeRow(item, options)));
    body.appendChild(list);

    container.append(header, body);
    resultsEl.appendChild(container);
  });
};

const renderCinemaGroups = (groups) => {
  resultsEl.innerHTML = '';

  if (groups.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'Aucune séance ne correspond à votre recherche.';
    resultsEl.appendChild(empty);
    return;
  }

  groups.forEach(({ title, items, meta }) => {
    const container = document.createElement('article');
    container.className = 'group';
    container.dataset.collapsible = 'cinema';
    container.dataset.cinemaKey = title;

    const header = document.createElement('div');
    header.className = 'group__header';
    header.setAttribute('role', 'button');
    header.setAttribute('tabindex', '0');
    const isExpanded = state.expandedCinemas.has(title);
    header.setAttribute('aria-expanded', String(isExpanded));

    const titleEl = document.createElement('h2');
    titleEl.className = 'group__title';
    titleEl.textContent = title;

    const metaEl = document.createElement('div');
    metaEl.className = 'group__meta';
    metaEl.textContent = meta;

    header.append(titleEl, metaEl);
    container.appendChild(header);

    const body = document.createElement('div');
    body.className = 'group__body';
    body.hidden = !isExpanded;
    container.classList.toggle('is-collapsed', !isExpanded);

    const byDate = Array.from(groupBy(items, (item) => item.dateISO))
      .map(([dateISO, dateItems]) => ({
        dateISO,
        items: dateItems
      }))
      .sort((a, b) => a.dateISO.localeCompare(b.dateISO));

    const MAX_DATES_PREVIEW = 3;
    const hiddenSections = [];

    byDate.forEach(({ dateISO, items: dateItems }, index) => {
      const section = document.createElement('div');
      section.className = 'group__section';

      const sectionHeader = document.createElement('div');
      sectionHeader.className = 'group__section-header';

      const sectionTitle = document.createElement('h3');
      sectionTitle.className = 'group__section-title';
      sectionTitle.textContent = formatDateFR(dateISO);

      sectionHeader.append(sectionTitle);
      section.appendChild(sectionHeader);

      const list = document.createElement('div');
      list.className = 'showtimes';
      dateItems.forEach((item) =>
        list.appendChild(buildShowtimeRow(item, { omitCinema: true, omitDate: true }))
      );
      section.appendChild(list);
      body.appendChild(section);
    });

    container.appendChild(body);
    resultsEl.appendChild(container);
  });
};

const sortItemsChronologically = (items) =>
  [...items].sort((a, b) => {
    if (a.timeMinutes !== b.timeMinutes) return a.timeMinutes - b.timeMinutes;
    return a.movie_title.localeCompare(b.movie_title, 'fr');
  });

const renderDateGroups = (groups) => {
  resultsEl.innerHTML = '';

  if (groups.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'Aucune séance ne correspond à votre recherche.';
    resultsEl.appendChild(empty);
    return;
  }

  groups.forEach(({ title, items, meta }) => {
    const container = document.createElement('article');
    container.className = 'group';

    const header = document.createElement('div');
    header.className = 'group__header';

    const titleEl = document.createElement('h2');
    titleEl.className = 'group__title';
    titleEl.textContent = title;

    const metaEl = document.createElement('div');
    metaEl.className = 'group__meta';
    metaEl.textContent = meta;

    header.append(titleEl, metaEl);
    container.appendChild(header);

    const byCinema = Array.from(groupBy(items, (item) => item.cinemaKey))
      .map(([key, cinemaItems]) => ({
        cinema: formatCinemaName(cinemaItems[0]?.cinema ?? key),
        items: sortItemsChronologically(cinemaItems)
      }))
      .sort((a, b) => a.cinema.localeCompare(b.cinema, 'fr'));

    byCinema.forEach(({ cinema, items: cinemaItems }) => {
      const section = document.createElement('div');
      section.className = 'group__section';

      const sectionHeader = document.createElement('div');
      sectionHeader.className = 'group__section-header';

      const sectionTitle = document.createElement('h3');
      sectionTitle.className = 'group__section-title';
      sectionTitle.textContent = formatCinemaName(cinema);

      sectionHeader.append(sectionTitle);
      section.appendChild(sectionHeader);

      const list = document.createElement('div');
      list.className = 'showtimes';
      cinemaItems.forEach((item) =>
        list.appendChild(buildShowtimeRow(item, { omitCinema: true, omitDate: true }))
      );
      section.appendChild(list);
      container.appendChild(section);
    });

    resultsEl.appendChild(container);
  });
};

const renderFilmGroups = (groups) => {
  resultsEl.innerHTML = '';

  if (groups.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = 'Aucune séance ne correspond à votre recherche.';
    resultsEl.appendChild(empty);
    return;
  }

  groups.forEach(({ title, items, meta }) => {
    const container = document.createElement('article');
    container.className = 'group';
    container.dataset.layout = 'film';

    const header = document.createElement('div');
    header.className = 'group__header';

    const content = document.createElement('div');
    content.className = 'group__content';

    const titleEl = document.createElement('h2');
    titleEl.className = 'group__title';
    const titleLink = document.createElement('a');
    titleLink.className = 'group__title-link';
    titleLink.href = `movie.html?title=${encodeURIComponent(title)}`;
    titleLink.textContent = title;
    titleEl.appendChild(titleLink);
    content.appendChild(titleEl);

    const movieData = moviesByTitle.get(normalize(title));
    if (movieData?.blurb) {
      const blurb = document.createElement('p');
      blurb.className = 'group__film-blurb';
      blurb.textContent = decodeEntities(movieData.blurb);
      content.appendChild(blurb);
    }
    if (movieData) {
      const metaLine = document.createElement('p');
      metaLine.className = 'group__film-meta';
      const metaParts = [];
      if (movieData.director) metaParts.push(decodeEntities(movieData.director));
      if (movieData.cast) metaParts.push(`Avec ${decodeEntities(movieData.cast)}`);
      if (movieData.release_date) {
        const year = String(movieData.release_date).slice(0, 4);
        if (year) metaParts.push(year);
      }
      metaLine.textContent = metaParts.join(' · ');
      if (metaLine.textContent) content.appendChild(metaLine);
    }

    const media = document.createElement('div');
    media.className = 'group__media';
    const img = document.createElement('img');
    img.className = 'group__poster';
    img.alt = movieData?.movie_title ? `Affiche de ${movieData.movie_title}` : 'Affiche du film';
    setPosterImage(img, movieData);
    media.appendChild(img);

    const hideBtn = document.createElement('button');
    hideBtn.className = 'group__hide';
    hideBtn.type = 'button';
    hideBtn.setAttribute('aria-label', `Masquer ${title}`);
    hideBtn.textContent = '×';
    hideBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      state.hiddenMovies.add(title);
      container.remove();
    });

    const hideWrap = document.createElement('div');
    hideWrap.className = 'group__hide-wrap';
    hideWrap.appendChild(hideBtn);

    const headRow = document.createElement('div');
    headRow.className = 'group__head-row';
    headRow.append(hideWrap, content, media);

    header.append(headRow);

    container.appendChild(header);

    let touchStartX = null;
    let touchStartY = null;
    container.addEventListener('touchstart', (event) => {
      if (event.target.closest('a, button')) return;
      const touch = event.touches[0];
      touchStartX = touch.clientX;
      touchStartY = touch.clientY;
    }, { passive: true });

    container.addEventListener('touchend', (event) => {
      if (touchStartX === null || touchStartY === null) return;
      const touch = event.changedTouches[0];
      const deltaX = touch.clientX - touchStartX;
      const deltaY = touch.clientY - touchStartY;
      touchStartX = null;
      touchStartY = null;
      if (Math.abs(deltaY) > 60) return;
      if (deltaX < -80) {
        state.hiddenMovies.add(title);
        container.remove();
      }
    });

    const byDate = Array.from(groupBy(items, (item) => item.dateISO))
      .map(([dateISO, dateItems]) => ({
        dateISO,
        items: sortItemsChronologically(dateItems)
      }))
      .sort((a, b) => a.dateISO.localeCompare(b.dateISO));

    const MAX_DATES_PREVIEW = 3;
    const hiddenSections = [];

    byDate.forEach(({ dateISO, items: dateItems }, index) => {
      const section = document.createElement('div');
      section.className = 'group__section';

      const sectionHeader = document.createElement('div');
      sectionHeader.className = 'group__section-header';

      const sectionTitle = document.createElement('h3');
      sectionTitle.className = 'group__section-title';
      sectionTitle.textContent = formatDateFR(dateISO);

      sectionHeader.append(sectionTitle);
      section.appendChild(sectionHeader);

      const list = document.createElement('div');
      list.className = 'showtimes';
      dateItems.forEach((item) =>
        list.appendChild(buildShowtimeRow(item, { omitMovie: true, omitDate: true, omitCinema: false }))
      );
      section.appendChild(list);
      if (index >= MAX_DATES_PREVIEW) {
        section.hidden = true;
        hiddenSections.push(section);
      }
      content.appendChild(section);
    });

    if (hiddenSections.length) {
      const toggle = document.createElement('button');
      toggle.className = 'show-more';
      toggle.type = 'button';
      toggle.textContent = 'Voir plus';
      toggle.dataset.expanded = 'false';
      toggle.addEventListener('click', () => {
        const expanded = toggle.dataset.expanded === 'true';
        if (expanded) {
          hiddenSections.forEach((section) => {
            section.hidden = true;
          });
          toggle.textContent = 'Voir plus';
          toggle.dataset.expanded = 'false';
        } else {
          hiddenSections.forEach((section) => {
            section.hidden = false;
          });
          toggle.textContent = 'Voir moins';
          toggle.dataset.expanded = 'true';
        }
      });
      content.appendChild(toggle);
    }

    resultsEl.appendChild(container);
  });
};

const buildFilteredList = () => {
  const todayISO = getTodayISO();
  return records
    .filter((item) => {
      if (!state.showAllDates && item.dateISO < todayISO) {
        return false;
      }
      if (state.movieFilter !== 'all' && item.movie_title !== state.movieFilter) {
        return false;
      }
      const version = (item.version || '').toUpperCase();
      const originalLanguage = (item.original_language || '').toLowerCase();
      const isVOF = !version && originalLanguage === 'fr';
      if (version === 'VOST' && !state.versionFilters.vost) {
        return false;
      }
      if (version === 'VF' && !state.versionFilters.vf) {
        return false;
      }
      if (isVOF && !state.versionFilters.vof) {
        return false;
      }
      if (state.hiddenMovies.has(item.movie_title)) {
        return false;
      }
      if (state.cinemaFilters.size && !state.cinemaFilters.has(item.cinema)) {
        return false;
      }
      return true;
    })
    .sort((a, b) => {
      if (a.dateISO !== b.dateISO) return a.dateISO.localeCompare(b.dateISO);
      return a.timeMinutes - b.timeMinutes;
    });
};

const render = () => {
  const filtered = buildFilteredList();

  if (state.mode === 'cinema') {
    const groups = Array.from(
      groupBy(filtered, (item) => item.cinemaKey)
    )
      .map(([key, items]) => {
        const cinema = formatCinemaName(items[0]?.cinema ?? key);
        return {
          title: cinema,
          items,
          meta: `${items.length} séance${items.length > 1 ? 's' : ''}`,
          showCopy: false
        };
      })
      .sort((a, b) => a.title.localeCompare(b.title, 'fr'));

    renderCinemaGroups(groups);
    initCinemaCollapsibles();
    return;
  }

  if (state.mode === 'date') {
    const groups = Array.from(
      groupBy(filtered, (item) => item.dateISO)
    )
      .map(([dateISO, items]) => ({
        title: formatDateFR(dateISO),
        items,
        meta: `${items.length} séance${items.length > 1 ? 's' : ''}`,
        showCopy: false
      }))
      .sort((a, b) => {
        const dateA = a.items[0]?.dateISO ?? '';
        const dateB = b.items[0]?.dateISO ?? '';
        return dateA.localeCompare(dateB);
      });

    renderDateGroups(groups);
    return;
  }

  const groups = Array.from(
    groupBy(filtered, (item) => item.movieKey)
  )
    .map(([key, items]) => {
      const movie = items[0]?.movie_title ?? key;
      return {
        title: movie,
        items,
        meta: `${items.length} séance${items.length > 1 ? 's' : ''}`,
        showCopy: false
      };
    })
    .sort((a, b) => a.title.localeCompare(b.title, 'fr'));

  renderFilmGroups(groups);
};

const initCinemaCollapsibles = () => {
  const headers = Array.from(document.querySelectorAll('.group[data-collapsible="cinema"] .group__header'));
  headers.forEach((header) => {
    const container = header.closest('.group');
    const body = container ? container.querySelector('.group__body') : null;
    if (!container || !body) return;

    const toggle = () => {
      const expanded = header.getAttribute('aria-expanded') === 'true';
      const nextExpanded = !expanded;
      header.setAttribute('aria-expanded', String(nextExpanded));
      body.hidden = !nextExpanded;
      container.classList.toggle('is-collapsed', !nextExpanded);
      const cinemaKey = container.dataset.cinemaKey;
      if (cinemaKey) {
        if (nextExpanded) {
          state.expandedCinemas.add(cinemaKey);
        } else {
          state.expandedCinemas.delete(cinemaKey);
        }
      }
    };

    header.addEventListener('click', toggle);
    header.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      toggle();
    });

    const expanded = header.getAttribute('aria-expanded') === 'true';
    body.hidden = !expanded;
    container.classList.toggle('is-collapsed', !expanded);
  });
};

const initFilmCollapsibles = () => {
  const headers = Array.from(document.querySelectorAll('.group[data-collapsible="film"] .group__header'));
  headers.forEach((header) => {
    const container = header.closest('.group');
    const body = container ? container.querySelector('.group__body') : null;
    if (!container || !body) return;

    const toggle = () => {
      const expanded = header.getAttribute('aria-expanded') === 'true';
      const nextExpanded = !expanded;
      header.setAttribute('aria-expanded', String(nextExpanded));
      body.hidden = !nextExpanded;
      container.classList.toggle('is-collapsed', !nextExpanded);
      const groupKey = container.dataset.groupKey;
      if (groupKey) {
        if (nextExpanded) {
          state.expandedMovies.add(groupKey);
        } else {
          state.expandedMovies.delete(groupKey);
        }
      }
    };

    header.addEventListener('click', toggle);
    header.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      toggle();
    });

    const expanded = header.getAttribute('aria-expanded') === 'true';
    body.hidden = !expanded;
    container.classList.toggle('is-collapsed', !expanded);
  });
};

const updateCinemaFilterVisibility = () => {
  const hidden = state.mode === 'cinema';
  cinemaFilterWrapEl.style.display = hidden ? 'none' : 'flex';
};

const renderLastUpdated = () => {
  if (!lastUpdatedEl) return;
  const stamp = window.PROGRAM_LAST_UPDATED;
  if (!stamp) {
    lastUpdatedEl.textContent = '';
    return;
  }
  const date = new Date(stamp);
  if (Number.isNaN(date.getTime())) {
    lastUpdatedEl.textContent = '';
    return;
  }
  const formatted = new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(date);
  lastUpdatedEl.textContent = `Dernière mise à jour : ${formatted}`;
};


const initTabs = () => {
  const buttons = Array.from(document.querySelectorAll('.segment__btn'));

  const setActive = (button, options = {}) => {
    buttons.forEach((btn) => {
      const isActive = btn === button;
      btn.setAttribute('aria-selected', String(isActive));
    });
    state.mode = button.dataset.mode;
    updateCinemaFilterVisibility();
    if (!options.silent) render();
  };

  buttons.forEach((button, index) => {
    button.addEventListener('click', () => setActive(button));
    button.addEventListener('keydown', (event) => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
      event.preventDefault();
      const dir = event.key === 'ArrowRight' ? 1 : -1;
      const nextIndex = (index + dir + buttons.length) % buttons.length;
      buttons[nextIndex].focus();
      setActive(buttons[nextIndex]);
    });
  });

  const initial = buttons.find((btn) => btn.getAttribute('aria-selected') === 'true') || buttons[0];
  if (initial) {
    setActive(initial, { silent: true });
  }
};

movieFilterEl.addEventListener('change', (event) => {
  state.movieFilter = event.target.value;
  render();
});

vfFilterEl.addEventListener('change', (event) => {
  state.versionFilters.vf = event.target.checked;
  updateVersionSummary();
  render();
});

vostFilterEl.addEventListener('change', (event) => {
  state.versionFilters.vost = event.target.checked;
  updateVersionSummary();
  render();
});

vofFilterEl.addEventListener('change', (event) => {
  state.versionFilters.vof = event.target.checked;
  updateVersionSummary();
  render();
});


showAllDatesEl.addEventListener('change', (event) => {
  state.showAllDates = event.target.checked;
  render();
});

versionDropdownButton?.addEventListener('click', (event) => {
  event.stopPropagation();
  toggleDropdown(versionDropdownButton, versionDropdownPanel);
});

cinemaDropdownButton?.addEventListener('click', (event) => {
  event.stopPropagation();
  toggleDropdown(cinemaDropdownButton, cinemaDropdownPanel);
});

versionDropdownPanel?.addEventListener('click', (event) => {
  event.stopPropagation();
});

cinemaDropdownPanel?.addEventListener('click', (event) => {
  event.stopPropagation();
});

document.addEventListener('click', () => {
  closeDropdowns();
});

buildMovieOptions();
buildCinemaOptions();
updateVersionSummary();
updateCinemaSummary();
initTabs();
updateCinemaFilterVisibility();
renderLastUpdated();
render();
