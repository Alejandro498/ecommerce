(function () {
  var root = document.getElementById('pc-assistant-root');
  if (!root) return;

  var chatUrl = root.getAttribute('data-chat-url') || '';
  var addBuildUrl = root.getAttribute('data-add-build-url') || '';
  var storageKey = root.getAttribute('data-storage-key') || 'pcbuilder.assistant.v2';
  var fab = document.getElementById('pc-assistant-fab');
  var tip = document.getElementById('pc-assistant-tip');
  var panel = document.getElementById('pc-assistant-panel');
  var log = document.getElementById('pc-assistant-log');
  var scrollBox = document.getElementById('pc-assistant-scroll');
  var form = document.getElementById('pc-assistant-form');
  var input = document.getElementById('pc-assistant-input');
  var sendBtn = document.getElementById('pc-assistant-send');
  var status = document.getElementById('pc-assistant-status');
  var clearBtn = document.getElementById('pc-assistant-clear');
  var closeBtn = document.getElementById('pc-assistant-close');
  var tabId = 'tab-' + Math.random().toString(36).slice(2);
  var applyingRemote = false;
  var WELCOME =
    'Hola. ¿Para qué quieres la PC y más o menos cuánto puedes gastar?\n' +
    'Por ejemplo: “Quiero jugar GTA a 1080 alto, soy principiante, prefiero AMD, traigo 18 mil”';

  var state = defaultState();

  function defaultState() {
    return {
      version: 2,
      open: false,
      messages: [{ who: 'welcome', text: WELCOME }],
      history: [],
      builds: [],
      priorities: [],
      carouselIndex: 0,
      status: '',
      updatedAt: Date.now(),
      sourceTab: tabId,
    };
  }

  function csrfToken() {
    var node = root.querySelector('[name=csrfmiddlewaretoken]');
    if (node && node.value) return node.value;
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function money(value) {
    return '$ ' + Number(value || 0).toLocaleString('es-MX');
  }

  function loadState() {
    try {
      var raw = localStorage.getItem(storageKey);
      if (!raw) return defaultState();
      var parsed = JSON.parse(raw);
      if (!parsed || (parsed.version !== 1 && parsed.version !== 2)) return defaultState();
      parsed.version = 2;
      if (!Array.isArray(parsed.messages) || !parsed.messages.length) {
        parsed.messages = [{ who: 'welcome', text: WELCOME }];
      }
      parsed.history = Array.isArray(parsed.history) ? parsed.history : [];
      parsed.builds = Array.isArray(parsed.builds) ? parsed.builds : [];
      parsed.priorities = Array.isArray(parsed.priorities) ? parsed.priorities : [];
      parsed.carouselIndex = Number(parsed.carouselIndex) || 0;
      return parsed;
    } catch (error) {
      return defaultState();
    }
  }

  function saveState() {
    if (applyingRemote) return;
    state.updatedAt = Date.now();
    state.sourceTab = tabId;
    try {
      localStorage.setItem(storageKey, JSON.stringify(state));
    } catch (error) {}
  }

  function updateAttention() {
    if (tip) tip.hidden = !!state.open;
    fab.classList.toggle('is-settled', state.open);
    fab.classList.toggle('is-open', state.open);
    fab.setAttribute('aria-expanded', state.open ? 'true' : 'false');
  }

  function setOpen(open) {
    state.open = !!open;
    panel.hidden = !state.open;
    updateAttention();
    if (state.open) {
      input.focus();
      scrollChatToBottom();
    }
    saveState();
  }

  function scrollChatToBottom() {
    if (!scrollBox) return;
    scrollBox.scrollTop = scrollBox.scrollHeight;
  }

  function revealCarousel() {
    if (!scrollBox) return;
    var carousel = log.querySelector('.pc-assistant-carousel');
    if (!carousel) {
      scrollChatToBottom();
      return;
    }
    var boxRect = scrollBox.getBoundingClientRect();
    var cardRect = carousel.getBoundingClientRect();
    scrollBox.scrollTop += (cardRect.top - boxRect.top) - 6;
  }

  function cartButtonHtml(build) {
    if (!build.can_add_to_cart || !(build.product_ids || []).length) {
      return '<p class="pc-assistant-note">Alguna pieza no está en la tienda.</p>';
    }
    var inputs = (build.product_ids || []).map(function (id) {
      return '<input type="hidden" name="product_id" value="' + escapeHtml(id) + '">';
    }).join('');
    return (
      '<form method="post" action="' + escapeHtml(addBuildUrl) + '" class="pc-assistant-cart-form">' +
        '<input type="hidden" name="csrfmiddlewaretoken" value="' + escapeHtml(csrfToken()) + '">' +
        inputs +
        '<button type="submit" class="btn btn-success btn-sm btn-block">Agregar al carrito</button>' +
      '</form>'
    );
  }

  function buildCardHtml(build) {
    var caseImg = '';
    var cpuImg = '';
    var gpuImg = '';
    (build.parts || []).forEach(function (part) {
      if (part.slot === 'case' && part.image) caseImg = part.image;
      if (part.slot === 'cpu' && part.image) cpuImg = part.image;
      if (part.slot === 'video-card' && part.image) gpuImg = part.image;
    });
    var images = build.images || {};
    caseImg = caseImg || images.case || '';
    cpuImg = cpuImg || images.cpu || '';
    gpuImg = gpuImg || images['video-card'] || '';

    function thumb(src) {
      if (!src) return '<div class="pc-assistant-thumb" aria-hidden="true"></div>';
      return (
        '<div class="pc-assistant-thumb">' +
          '<img src="' + escapeHtml(src) + '" alt="" loading="lazy">' +
        '</div>'
      );
    }
    var media =
      '<div class="pc-assistant-build-media">' +
        thumb(caseImg) +
        thumb(cpuImg) +
        thumb(gpuImg) +
      '</div>';

    var parts = (build.parts || []).map(function (part) {
      var name = part.url && part.url !== '#'
        ? '<a href="' + escapeHtml(part.url) + '">' + escapeHtml(part.name) + '</a>'
        : escapeHtml(part.name);
      return (
        '<div class="pc-assistant-part">' +
          '<div class="pc-assistant-part-label">' + escapeHtml(part.label) + '</div>' +
          '<div class="pc-assistant-part-name">' + name + '</div>' +
          '<div class="pc-assistant-part-price">' + money(part.price) + '</div>' +
        '</div>'
      );
    }).join('');

    var score = build.score != null ? build.score : build.fitness;
    var scoreHtml = score != null
      ? '<span class="pc-assistant-build-score" title="Aptitud del motor (calidad + presupuesto)">Score ' +
          escapeHtml(score) + '/100</span>'
      : '';

    return (
      '<article class="pc-assistant-build">' +
        media +
        '<div class="pc-assistant-build-head">' +
          '<div class="pc-assistant-build-title">Opción ' + escapeHtml(build.rank) + '</div>' +
          scoreHtml +
        '</div>' +
        '<p class="pc-assistant-build-summary">' + escapeHtml(build.summary || '') + '</p>' +
        '<div class="pc-assistant-parts">' + parts + '</div>' +
        '<div class="pc-assistant-build-footer">' +
          '<div class="pc-assistant-build-price">' + money(build.total_price) + '</div>' +
          cartButtonHtml(build) +
        '</div>' +
      '</article>'
    );
  }

  function prioritiesHtml() {
    if (!(state.priorities || []).length) return '';
    var badges = state.priorities.map(function (item) {
      return (
        '<span class="badge badge-light border mr-1 mb-1">' +
          escapeHtml(item.label) + ': ' + escapeHtml(item.prioridad) +
        '</span>'
      );
    }).join('');
    return '<div class="pc-assistant-priorities">' + badges + '</div>';
  }

  function clampCarouselIndex() {
    var count = (state.builds || []).length;
    if (!count) {
      state.carouselIndex = 0;
      return;
    }
    if (state.carouselIndex < 0) state.carouselIndex = 0;
    if (state.carouselIndex >= count) state.carouselIndex = count - 1;
  }

  function renderCarouselInto(host) {
    clampCarouselIndex();
    var builds = state.builds || [];
    var index = state.carouselIndex;
    var build = builds[index];
    if (!build) {
      host.innerHTML = '';
      return;
    }

    var dots = builds.map(function (_item, i) {
      return (
        '<button type="button" class="pc-assistant-dot' + (i === index ? ' is-active' : '') +
        '" data-carousel-goto="' + i + '" aria-label="Opción ' + (i + 1) + '"></button>'
      );
    }).join('');

    host.innerHTML =
      prioritiesHtml() +
      '<div class="pc-assistant-carousel-nav">' +
        '<button type="button" data-carousel-step="-1" aria-label="Anterior"' +
          (index <= 0 ? ' disabled' : '') + '>&lsaquo;</button>' +
        '<div class="pc-assistant-carousel-meta">Opción ' + (index + 1) + ' de ' + builds.length + '</div>' +
        '<button type="button" data-carousel-step="1" aria-label="Siguiente"' +
          (index >= builds.length - 1 ? ' disabled' : '') + '>&rsaquo;</button>' +
      '</div>' +
      '<div class="pc-assistant-dots">' + dots + '</div>' +
      buildCardHtml(build);
  }

  function renderAll() {
    log.innerHTML = '';
    (state.messages || []).forEach(function (item) {
      if (item.who === 'carousel') {
        var carousel = document.createElement('div');
        carousel.className = 'pc-assistant-carousel';
        carousel.setAttribute('data-carousel', '1');
        renderCarouselInto(carousel);
        log.appendChild(carousel);
        return;
      }
      var wrap = document.createElement('div');
      if (item.who === 'user') {
        wrap.className = 'pc-assistant-bubble pc-assistant-bubble-user';
      } else if (item.who === 'welcome') {
        wrap.className = 'pc-assistant-bubble pc-assistant-bubble-welcome';
      } else {
        wrap.className = 'pc-assistant-bubble pc-assistant-bubble-bot';
      }
      wrap.textContent = item.text || '';
      log.appendChild(wrap);
    });

    status.textContent = state.status || '';
    panel.hidden = !state.open;
    updateAttention();

    if ((state.builds || []).length) {
      requestAnimationFrame(revealCarousel);
    } else {
      scrollChatToBottom();
    }
  }

  function ensureCarouselMessage() {
    var hasCarousel = (state.messages || []).some(function (item) {
      return item.who === 'carousel';
    });
    if (!hasCarousel) {
      state.messages.push({ who: 'carousel' });
    }
  }

  function removeCarouselMessage() {
    state.messages = (state.messages || []).filter(function (item) {
      return item.who !== 'carousel';
    });
  }

  function appendMessage(text, who) {
    state.messages.push({ who: who, text: text });
    renderAll();
    saveState();
  }

  function setBuilds(builds, priorities) {
    state.builds = builds || [];
    state.priorities = priorities || [];
    state.carouselIndex = 0;
    removeCarouselMessage();
    if (state.builds.length) {
      ensureCarouselMessage();
    }
    renderAll();
    saveState();
  }

  function moveCarousel(delta) {
    if (!(state.builds || []).length) return;
    state.carouselIndex += delta;
    clampCarouselIndex();
    renderAll();
    saveState();
  }

  function goToCarousel(index) {
    state.carouselIndex = index;
    clampCarouselIndex();
    renderAll();
    saveState();
  }

  function printDebug(debug) {
    if (!debug) return;
    console.group('%cAsistente de compras', 'color:#0d6efd;font-weight:bold;font-size:13px');
    console.log('%cProcedimiento', 'font-weight:bold');
    (debug.procedimiento || []).forEach(function (step) { console.log(step); });
    console.log('Motor:', debug.engine, '| Selección:', debug.seleccion);
    console.log('%cPrioridades Mamdani', 'font-weight:bold');
    console.table(debug.prioridades || []);
    console.log('%cConfiguraciones', 'font-weight:bold');
    console.table((debug.builds || []).map(function (build) {
      return { rank: build.rank, aptitud: build.aptitud, total_mxn: build.total_mxn, resumen: build.resumen };
    }));
    console.groupEnd();
  }

  function postChat(body) {
    return fetch(chatUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken(),
      },
      body: JSON.stringify(body),
    }).then(function (response) {
      return response.json().then(function (data) {
        return { ok: response.ok, data: data };
      });
    });
  }

  function clearConversation() {
    state = defaultState();
    state.open = true;
    renderAll();
    saveState();
    input.focus();
  }

  fab.addEventListener('click', function () {
    setOpen(!state.open);
  });
  if (tip) {
    tip.addEventListener('click', function () {
      setOpen(true);
    });
  }
  closeBtn.addEventListener('click', function () {
    setOpen(false);
  });
  clearBtn.addEventListener('click', function () {
    clearConversation();
  });

  log.addEventListener('click', function (event) {
    var stepBtn = event.target.closest('[data-carousel-step]');
    if (stepBtn) {
      moveCarousel(Number(stepBtn.getAttribute('data-carousel-step')) || 0);
      return;
    }
    var gotoBtn = event.target.closest('[data-carousel-goto]');
    if (gotoBtn) {
      goToCarousel(Number(gotoBtn.getAttribute('data-carousel-goto')) || 0);
    }
  });

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var text = (input.value || '').trim();
    if (!text) return;
    appendMessage(text, 'user');
    state.history.push({ role: 'user', content: text });
    input.value = '';
    state.status = 'Interpretando…';
    status.textContent = state.status;
    saveState();
    sendBtn.disabled = true;

    postChat({ message: text, history: state.history, build: false })
      .then(function (result) {
        var data = result.data || {};
        var engine = data.interpreter || '?';
        var reply = data.reply || 'No pude procesar el mensaje.';
        appendMessage(reply, 'bot');
        state.history.push({ role: 'assistant', content: reply });
        saveState();
        console.log('Asistente interprete:', engine, data);

        if (!data.ready) {
          state.status = 'Te falta un dato para armarte la PC';
          status.textContent = state.status;
          saveState();
          return null;
        }

        state.status = 'Armando tus opciones…';
        status.textContent = state.status;
        saveState();
        return postChat({
          build: true,
          use_case: data.use_case,
          budget: data.budget,
          prefs: data.prefs || {},
          interpreter: engine,
          message: text,
          history: state.history,
        }).then(function (buildResult) {
          var built = (buildResult && buildResult.data) || {};
          if (built.reply) {
            appendMessage(built.reply, 'bot');
            state.history.push({ role: 'assistant', content: built.reply });
          }
          setBuilds(built.builds || [], built.priorities || []);
          state.status = 'Listo. Desliza entre opciones o pide otro presupuesto.';
          status.textContent = state.status;
          printDebug(built.debug);
          saveState();
        });
      })
      .catch(function (error) {
        appendMessage('Uy, se me fue la conexión. ¿Lo intentamos de nuevo?', 'bot');
        state.status = String(error);
        status.textContent = state.status;
        saveState();
      })
      .finally(function () {
        sendBtn.disabled = false;
        if (state.open) input.focus();
      });
  });

  window.addEventListener('storage', function (event) {
    if (event.key !== storageKey || !event.newValue) return;
    try {
      var incoming = JSON.parse(event.newValue);
      if (!incoming || incoming.sourceTab === tabId) return;
      applyingRemote = true;
      state = incoming;
      state.version = 2;
      if (!Array.isArray(state.messages) || !state.messages.length) {
        state.messages = [{ who: 'welcome', text: WELCOME }];
      }
      renderAll();
      applyingRemote = false;
    } catch (error) {
      applyingRemote = false;
    }
  });

  state = loadState();
  // Migración: si hay builds sin mensaje carrusel, lo insertamos.
  if ((state.builds || []).length) {
    ensureCarouselMessage();
  }
  renderAll();
})();
