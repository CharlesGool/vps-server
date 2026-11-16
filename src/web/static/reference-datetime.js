// Date and time controls in the template's style, as an enhancement of native inputs.
// A native <input type="date"> or <input type="time"> stays in the form (hidden) and keeps the
// value the server reads; the visible control is made of numeric segments (always 24-hour, with
// seconds when the input has step < 60) and, for dates, a calendar popover.
(() => {
  const pad = (value, length = 2) => String(value).padStart(length, '0');
  const lang = document.documentElement.lang || undefined;
  const fire = (input) => {
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  };
  const labelsOf = (input) => {
    try { return JSON.parse(input.dataset.labels || '{}'); } catch (error) { return {}; }
  };
  const fieldLabel = (input) => input.closest('label')?.querySelector('span')?.textContent?.trim() || input.name;

  // One numeric segment: type digits, arrow keys step, it moves on when full.
  const segment = (name, length, min, max, label, onChange, next) => {
    const element = document.createElement('input');
    element.type = 'text';
    element.inputMode = 'numeric';
    element.maxLength = length;
    element.className = 'reference-segment';
    element.dataset.length = String(length);
    element.setAttribute('aria-label', label);
    element.placeholder = '0'.repeat(length);
    element.autocomplete = 'off';
    element.spellcheck = false;
    const set = (value) => {
      element.value = value === '' ? '' : pad(Math.min(max, Math.max(min, value)), length);
      onChange();
    };
    element.addEventListener('input', () => {
      element.value = element.value.replace(/\D/g, '').slice(0, length);
      if (element.value.length === length) {
        set(Number(element.value));
        next?.();
      } else {
        onChange();
      }
    });
    element.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
        event.preventDefault();
        const step = event.key === 'ArrowUp' ? 1 : -1;
        const current = element.value === '' ? (step > 0 ? min - 1 : max + 1) : Number(element.value);
        set(current + step > max ? min : current + step < min ? max : current + step);
      } else if (event.key === 'Backspace' && element.value === '' && element.previousElementSibling) {
        const previous = [...element.parentElement.querySelectorAll('.reference-segment')].reverse()
          .find((other) => other.compareDocumentPosition(element) & Node.DOCUMENT_POSITION_FOLLOWING);
        previous?.focus();
      }
    });
    element.addEventListener('focus', () => element.select());
    element.addEventListener('blur', () => { if (element.value !== '') set(Number(element.value)); });
    return { element, set, name };
  };
  const separator = (text) => {
    const span = document.createElement('span');
    span.className = 'reference-sep';
    span.setAttribute('aria-hidden', 'true');
    span.textContent = text;
    return span;
  };
  const hide = (native) => {
    native.classList.add('reference-native-input');
    native.tabIndex = -1;
    native.setAttribute('aria-hidden', 'true');
  };

  // ---- time -------------------------------------------------------------------------------
  document.querySelectorAll('input[type="time"]').forEach((native) => {
    const labels = labelsOf(native);
    const withSeconds = native.step !== '' && Number(native.step) < 60;
    const wrapper = document.createElement('div');
    wrapper.className = 'reference-time';
    wrapper.setAttribute('role', 'group');
    wrapper.setAttribute('aria-label', fieldLabel(native));
    const [hours = '', minutes = '', seconds = ''] = (native.value || '').split(':');
    const parts = [];
    const sync = () => {
      const values = parts.map((part) => part.element.value);
      native.value = values.every((value) => value !== '') ? values.join(':') : '';
      fire(native);
    };
    const focusNext = (index) => () => parts[index + 1]?.element.focus();
    parts.push(segment('h', 2, 0, 23, labels.hour || 'hour', sync, focusNext(0)));
    parts.push(segment('m', 2, 0, 59, labels.minute || 'minute', sync, focusNext(1)));
    if (withSeconds) parts.push(segment('s', 2, 0, 59, labels.second || 'second', sync, focusNext(2)));
    parts[0].element.value = hours;
    parts[1].element.value = minutes;
    if (withSeconds) parts[2].element.value = seconds || '00';
    parts.forEach((part, index) => {
      if (index) wrapper.append(separator(':'));
      wrapper.append(part.element);
    });
    native.before(wrapper);
    hide(native);
  });

  // ---- date -------------------------------------------------------------------------------
  const calendars = [];
  const closeAll = () => calendars.forEach((close) => close());
  document.querySelectorAll('input[type="date"]').forEach((native) => {
    const labels = labelsOf(native);
    const minimum = native.min || '';
    const wrapper = document.createElement('div');
    wrapper.className = 'reference-date';
    wrapper.setAttribute('role', 'group');
    wrapper.setAttribute('aria-label', fieldLabel(native));
    const [year0 = '', month0 = '', day0 = ''] = (native.value || '').split('-');
    const parts = [];
    const valid = () => {
      const [y, m, d] = parts.map((part) => Number(part.element.value));
      if (parts.some((part) => part.element.value === '')) return false;
      const date = new Date(y, m - 1, d);
      return date.getFullYear() === y && date.getMonth() === m - 1 && date.getDate() === d;
    };
    const sync = () => {
      native.value = valid() ? parts.map((part) => part.element.value).join('-') : '';
      fire(native);
    };
    const focusNext = (index) => () => parts[index + 1]?.element.focus();
    parts.push(segment('y', 4, 1, 9999, labels.year || 'year', sync, focusNext(0)));
    parts.push(segment('m', 2, 1, 12, labels.month || 'month', sync, focusNext(1)));
    parts.push(segment('d', 2, 1, 31, labels.day || 'day', sync));
    parts[0].element.value = year0;
    parts[1].element.value = month0;
    parts[2].element.value = day0;
    parts.forEach((part, index) => {
      if (index) wrapper.append(separator('-'));
      wrapper.append(part.element);
    });

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'reference-calendar-toggle';
    toggle.setAttribute('aria-label', labels.calendar || 'calendar');
    toggle.setAttribute('aria-haspopup', 'dialog');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.innerHTML = '<svg class="ui-icon" aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/></svg>';
    const popover = document.createElement('div');
    popover.className = 'reference-calendar';
    popover.setAttribute('role', 'dialog');
    popover.setAttribute('aria-label', labels.calendar || 'calendar');
    popover.hidden = true;
    const head = document.createElement('div');
    head.className = 'reference-calendar-head';
    const previous = document.createElement('button');
    previous.type = 'button';
    previous.textContent = '‹';
    previous.setAttribute('aria-label', labels.previous || 'previous month');
    const title = document.createElement('strong');
    const following = document.createElement('button');
    following.type = 'button';
    following.textContent = '›';
    following.setAttribute('aria-label', labels.next || 'next month');
    head.append(previous, title, following);
    const grid = document.createElement('div');
    grid.className = 'reference-calendar-grid';
    popover.append(head, grid);
    wrapper.append(toggle, popover);

    let shown = new Date();
    const render = () => {
      title.textContent = new Intl.DateTimeFormat(lang, { year: 'numeric', month: 'long' }).format(shown);
      grid.replaceChildren();
      const monday = new Date(2024, 0, 1);                     // a Monday: weekday names, Monday first
      for (let i = 0; i < 7; i += 1) {
        const name = document.createElement('span');
        name.textContent = new Intl.DateTimeFormat(lang, { weekday: 'narrow' }).format(new Date(2024, 0, 1 + i));
        grid.append(name);
      }
      const first = new Date(shown.getFullYear(), shown.getMonth(), 1);
      const offset = (first.getDay() + 6) % 7;
      for (let i = 0; i < offset; i += 1) grid.append(document.createElement('span'));
      const days = new Date(shown.getFullYear(), shown.getMonth() + 1, 0).getDate();
      const today = new Date();
      for (let day = 1; day <= days; day += 1) {
        const text = `${shown.getFullYear()}-${pad(shown.getMonth() + 1)}-${pad(day)}`;
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = String(day);
        button.disabled = minimum !== '' && text < minimum;
        button.setAttribute('aria-pressed', String(text === native.value));
        if (text === `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`) button.dataset.today = '';
        button.addEventListener('click', () => {
          const [y, m, d] = text.split('-');
          parts[0].element.value = y;
          parts[1].element.value = m;
          parts[2].element.value = d;
          sync();
          close();
          toggle.focus();
        });
        grid.append(button);
      }
    };
    const close = () => { popover.hidden = true; toggle.setAttribute('aria-expanded', 'false'); };
    calendars.push(close);
    toggle.addEventListener('click', () => {
      if (!popover.hidden) { close(); return; }
      closeAll();
      shown = native.value ? new Date(`${native.value}T00:00:00`) : new Date();
      shown.setDate(1);
      render();
      popover.hidden = false;
      toggle.setAttribute('aria-expanded', 'true');
    });
    previous.addEventListener('click', () => { shown.setMonth(shown.getMonth() - 1); render(); });
    following.addEventListener('click', () => { shown.setMonth(shown.getMonth() + 1); render(); });
    popover.addEventListener('keydown', (event) => { if (event.key === 'Escape') { close(); toggle.focus(); } });
    wrapper.addEventListener('focusout', (event) => { if (!wrapper.contains(event.relatedTarget)) close(); });
    native.before(wrapper);
    hide(native);
  });
})();
