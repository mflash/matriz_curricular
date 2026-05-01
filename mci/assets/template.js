(function () {
  'use strict';

  const COURSES = {{COURSES_JSON}};
  const REQUIREMENTS = {{REQUIREMENTS_JSON}};
  const CATEGORIES = {{CATEGORIES_JSON}};

  const courseMap = new Map(COURSES.map(c => [c.code, c]));
  const categoryColorMap = new Map(
    CATEGORIES
      .filter(c => typeof c.color === 'string' && c.color.trim() !== '')
      .map(c => [c.id, c.color])
  );

  // Responsive matrix scale
  function applyMatrixScale() {
    var matrixArea = document.querySelector('.matrix-area');
    var matrixCanvas = document.querySelector('.matrix-canvas');
    var legendPanel = document.querySelector('.legend-panel');
    if (!matrixArea || !matrixCanvas) return;

    var baseWidth = parseFloat(matrixArea.style.getPropertyValue('--matrix-base-w'));
    var baseHeight = parseFloat(matrixArea.style.getPropertyValue('--matrix-base-h'));
    if (!baseWidth || !baseHeight) return;

    var padding = 24;
    var isStacked = window.innerWidth <= 1200;
    var legendW = (!isStacked && legendPanel) ? (legendPanel.offsetWidth + 16) : 0;
    var availWidth = window.innerWidth - padding * 2 - legendW;
    var scale = Math.min(1, availWidth / baseWidth);
    var scaledW = baseWidth * scale;
    var scaledH = baseHeight * scale;

    matrixArea.style.width = scaledW + 'px';
    matrixArea.style.height = scaledH + 'px';
    matrixCanvas.style.transform = scale < 1 ? 'scale(' + scale + ')' : '';

    if (legendPanel) legendPanel.style.width = isStacked ? scaledW + 'px' : '';
  }

  applyMatrixScale();
  window.addEventListener('resize', applyMatrixScale);

  // Arrow visibility toggle
  const toggleArrows = document.getElementById('toggle-arrows');
  const arrowsLayer = document.querySelector('.arrows-layer');

  arrowsLayer.classList.add('hidden');

  toggleArrows.addEventListener('change', () => {
    arrowsLayer.classList.toggle('hidden', !toggleArrows.checked);
  });

  // Hover over cards
  const allCards = Array.from(document.querySelectorAll('.course-card'));
  const allArrows = Array.from(document.querySelectorAll('.arrow-group'));
  const forwardGraph = new Map();
  const reverseGraph = new Map();

  function addEdge(graph, from, to) {
    if (!from || !to) return;
    if (!graph.has(from)) graph.set(from, new Set());
    graph.get(from).add(to);
  }

  for (const req of REQUIREMENTS) {
    if (req.type === 'credit_requirement' || !req.from || !req.to) continue;
    addEdge(forwardGraph, req.from, req.to);
    addEdge(reverseGraph, req.to, req.from);
  }

  function collectReachable(startCode, graph) {
    const visited = new Set();
    const pending = [startCode];

    while (pending.length > 0) {
      const code = pending.pop();
      const neighbors = graph.get(code);
      if (!neighbors) continue;
      for (const next of neighbors) {
        if (visited.has(next)) continue;
        visited.add(next);
        pending.push(next);
      }
    }

    return visited;
  }

  function getRelated(code) {
    const prereqs = collectReachable(code, reverseGraph);
    const dependents = collectReachable(code, forwardGraph);
    const prerequisiteChain = new Set([...prereqs, code]);
    const dependentChain = new Set([code, ...dependents]);
    const related = new Set([...prerequisiteChain, ...dependentChain]);
    return { prereqs, dependents, prerequisiteChain, dependentChain, related };
  }

  function onCardEnter(code) {
    const { prerequisiteChain, dependentChain, related } = getRelated(code);

    allCards.forEach(card => {
      const c = card.dataset.code;
      card.classList.toggle('highlighted', related.has(c));
      card.classList.toggle('faded', !related.has(c));
    });

    arrowsLayer.classList.remove('hidden');

    allArrows.forEach(arrow => {
      const from = arrow.dataset.from;
      const to = arrow.dataset.to;
      const active = Boolean(from && to) && (
        (prerequisiteChain.has(from) && prerequisiteChain.has(to)) ||
        (dependentChain.has(from) && dependentChain.has(to))
      );
      arrow.style.display = active ? '' : 'none';
    });
  }

  function onCardLeave() {
    allCards.forEach(card => {
      card.classList.remove('highlighted', 'faded');
    });
    allArrows.forEach(arrow => {
      arrow.style.display = '';
    });
    arrowsLayer.classList.toggle('hidden', !toggleArrows.checked);
  }

  allCards.forEach(card => {
    card.addEventListener('mouseenter', () => onCardEnter(card.dataset.code));
    card.addEventListener('mouseleave', onCardLeave);
    card.addEventListener('focusin', () => onCardEnter(card.dataset.code));
    card.addEventListener('focusout', onCardLeave);
  });

  // Details popup
  const popup = document.getElementById('course-popup');
  const popupClose = popup.querySelector('.popup-close');
  const popupHeader = popup.querySelector('.popup-header');
  const defaultPopupHeaderColor = '#1a3a6b';

  function openPopup(code) {
    const course = courseMap.get(code);
    if (!course) return;

    const popupHeaderColor = course.category
      ? categoryColorMap.get(course.category)
      : null;
    popupHeader.style.background = popupHeaderColor || defaultPopupHeaderColor;

    document.getElementById('popup-code').textContent = course.code;
    document.getElementById('popup-name').textContent = course.name;
    document.getElementById('popup-hours').textContent = course.hours + ' h';
    document.getElementById('popup-credits').textContent = course.credits + ' cr';
    document.getElementById('popup-syllabus').textContent = course.syllabus || '—';

    const tagsEl = document.getElementById('popup-tags');
    tagsEl.innerHTML = '';
    course.tags.forEach(function (tag) {
      const span = document.createElement('span');
      span.className = 'tag tag-' + tag;
      span.textContent = tag;
      tagsEl.appendChild(span);
    });

    const prereqs = REQUIREMENTS
      .filter(function (r) { return r.to === code && r.from; })
      .map(function (r) {
        const c = courseMap.get(r.from);
        return { code: r.from, name: c ? c.name : '', desc: r.description };
      });
    const creditReq = REQUIREMENTS.find(function (r) {
      return r.type === 'credit_requirement' && r.to === code;
    });

    const prereqEl = document.getElementById('popup-prereqs');
    prereqEl.innerHTML = '';
    if (prereqs.length === 0 && !creditReq) {
      const none = document.createElement('span');
      none.className = 'popup-empty';
      none.textContent = 'Nenhum pré-requisito';
      prereqEl.appendChild(none);
    } else {
      const ul = document.createElement('ul');
      ul.className = 'popup-req-list';
      prereqs.forEach(function (p) {
        const li = document.createElement('li');
        li.className = 'popup-req-item';
        const codeSpan = document.createElement('span');
        codeSpan.className = 'popup-req-code';
        codeSpan.textContent = p.code;
        const nameSpan = document.createElement('span');
        nameSpan.className = 'popup-req-name';
        nameSpan.textContent = p.name + (p.desc ? ' (' + p.desc + ')' : '');
        li.appendChild(codeSpan);
        li.appendChild(nameSpan);
        ul.appendChild(li);
      });
      if (creditReq) {
        const li = document.createElement('li');
        li.className = 'popup-req-item';
        const span = document.createElement('span');
        span.className = 'popup-req-name';
        span.textContent = 'Mín. ' + creditReq.min_credits + ' créditos cursados';
        li.appendChild(span);
        ul.appendChild(li);
      }
      prereqEl.appendChild(ul);
    }

    const dependents = REQUIREMENTS
      .filter(function (r) { return r.from === code && r.to; })
      .map(function (r) {
        const c = courseMap.get(r.to);
        return { code: r.to, name: c ? c.name : '' };
      });

    const depsEl = document.getElementById('popup-dependents');
    depsEl.innerHTML = '';
    if (dependents.length === 0) {
      const none = document.createElement('span');
      none.className = 'popup-empty';
      none.textContent = 'Nenhuma dependência';
      depsEl.appendChild(none);
    } else {
      const ul = document.createElement('ul');
      ul.className = 'popup-req-list';
      dependents.forEach(function (d) {
        const li = document.createElement('li');
        li.className = 'popup-req-item';
        const codeSpan = document.createElement('span');
        codeSpan.className = 'popup-req-code';
        codeSpan.textContent = d.code;
        const nameSpan = document.createElement('span');
        nameSpan.className = 'popup-req-name';
        nameSpan.textContent = d.name;
        li.appendChild(codeSpan);
        li.appendChild(nameSpan);
        ul.appendChild(li);
      });
      depsEl.appendChild(ul);
    }

    popup.hidden = false;
    popupClose.focus();
  }

  function closePopup() {
    popup.hidden = true;
  }

  allCards.forEach(card => {
    card.addEventListener('click', () => openPopup(card.dataset.code));
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openPopup(card.dataset.code);
      }
    });
  });

  popupClose.addEventListener('click', closePopup);
  popup.addEventListener('click', e => { if (e.target === popup) closePopup(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closePopup(); });
})();
