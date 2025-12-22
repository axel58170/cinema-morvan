const program = window.PROGRAM || [];
const state = {
  mode: 'cinema',
  movieFilter: 'all',
  versionFilters: {
    vf: true,
    vost: true,
    vof: true
  },
  cinemaFilter: 'all',
  showAllDates: false,
  expandedCinemas: new Set(),
  expandedMovies: new Set()
};

const parseTimeToMinutes = (timeRaw) => {
  const match = timeRaw.match(/(\d{1,2})h(\d{2})/i);
  if (!match) return 0;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
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

const resultsEl = document.querySelector('#results');
const movieFilterEl = document.querySelector('#movieFilter');
const vfFilterEl = document.querySelector('#vfFilter');
const vostFilterEl = document.querySelector('#vostFilter');
const vofFilterEl = document.querySelector('#vofFilter');
const cinemaFilterEl = document.querySelector('#cinemaFilter');
const cinemaFilterWrapEl = document.querySelector('#cinemaFilterWrap');
const lastUpdatedEl = document.querySelector('#lastUpdated');
const dateToggleEl = document.querySelector('#dateToggle');

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

  cinemas.forEach((cinema) => {
    const option = document.createElement('option');
    option.value = cinema;
    option.textContent = cinema;
    cinemaFilterEl.appendChild(option);
  });
};

const formatCinemaName = (name) => {
  if (!name) return '';
  return name.split('–')[0].trim();
};

const buildShowtimeRow = (item, options = {}) => {
  const row = document.createElement('div');
  row.className = 'showtime';

  const cells = [];

  if (!options.omitCinema) {
    const cinema = document.createElement('div');
    cinema.textContent = formatCinemaName(item.cinema);
    cells.push(cinema);
  }

  if (!options.omitMovie) {
    const movie = document.createElement('div');
    movie.className = 'showtime__title';
    movie.textContent = item.movie_title;
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

  const time = document.createElement('div');
  time.textContent = item.timeRaw;
  cells.push(time);

  const version = document.createElement('div');
  version.textContent = item.version ?? '';
  cells.push(version);

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

    const titleEl = document.createElement('h2');
    titleEl.className = 'group__title';
    titleEl.textContent = title;

    const metaEl = document.createElement('div');
    metaEl.className = 'group__meta';
    metaEl.textContent = meta;

    header.append(titleEl, metaEl);

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

    byDate.forEach(({ dateISO, items: dateItems }) => {
      const section = document.createElement('div');
      section.className = 'group__section';

      const sectionHeader = document.createElement('div');
      sectionHeader.className = 'group__section-header';

      const sectionTitle = document.createElement('h3');
      sectionTitle.className = 'group__section-title';
      sectionTitle.textContent = formatDateFR(dateISO);

      const sectionMeta = document.createElement('div');
      sectionMeta.className = 'group__section-meta';
      sectionMeta.textContent = `${dateItems.length} séance${dateItems.length > 1 ? 's' : ''}`;

      sectionHeader.append(sectionTitle, sectionMeta);
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
      if (state.cinemaFilter !== 'all' && item.cinema !== state.cinemaFilter) {
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

    renderGroups(groups, { omitDate: true });
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

  renderGroups(groups, {
    omitMovie: true,
    showWeekday: true,
    collapsibleKey: 'film',
    isExpanded: (title) => state.expandedMovies.has(title)
  });
  initFilmCollapsibles();
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

const renderDateToggle = () => {
  if (!dateToggleEl) return;
  dateToggleEl.textContent = state.showAllDates ? 'À venir' : 'Afficher toutes les dates';
};

const toggleDateMode = () => {
  state.showAllDates = !state.showAllDates;
  renderDateToggle();
  render();
};

const initTabs = () => {
  const buttons = Array.from(document.querySelectorAll('.segment__btn'));

  const setActive = (button) => {
    buttons.forEach((btn) => {
      const isActive = btn === button;
      btn.setAttribute('aria-selected', String(isActive));
    });
    state.mode = button.dataset.mode;
    updateCinemaFilterVisibility();
    render();
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
};

movieFilterEl.addEventListener('change', (event) => {
  state.movieFilter = event.target.value;
  render();
});

vfFilterEl.addEventListener('change', (event) => {
  state.versionFilters.vf = event.target.checked;
  render();
});

vostFilterEl.addEventListener('change', (event) => {
  state.versionFilters.vost = event.target.checked;
  render();
});

vofFilterEl.addEventListener('change', (event) => {
  state.versionFilters.vof = event.target.checked;
  render();
});

cinemaFilterEl.addEventListener('change', (event) => {
  state.cinemaFilter = event.target.value;
  render();
});

dateToggleEl.addEventListener('click', toggleDateMode);

buildMovieOptions();
buildCinemaOptions();
initTabs();
updateCinemaFilterVisibility();
renderLastUpdated();
renderDateToggle();
render();
