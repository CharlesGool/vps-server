(() => {
  const pickers = [];
  const close = (picker, focus = false) => {
    picker.list.hidden = true;
    picker.trigger.setAttribute('aria-expanded', 'false');
    if (focus) picker.trigger.focus();
  };
  document.querySelectorAll('select').forEach((select, index) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'reference-select';
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'reference-select-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    const value = document.createElement('span');
    value.textContent = select.selectedOptions[0]?.textContent || '';
    const chevron = document.createElement('span');
    chevron.className = 'reference-select-chevron';
    chevron.setAttribute('aria-hidden', 'true');
    trigger.append(value, chevron);
    const list = document.createElement('div');
    list.className = 'reference-select-options';
    list.role = 'listbox';
    list.id = `reference-select-${index}`;
    list.hidden = true;
    trigger.setAttribute('aria-controls', list.id);
    const label = select.closest('label')?.firstChild?.textContent?.trim() || select.name;
    trigger.setAttribute('aria-label', `${label}: ${value.textContent}`);
    const options = [...select.options].map((original) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.role = 'option';
      button.textContent = original.textContent;
      button.setAttribute('aria-selected', String(original.selected));
      button.tabIndex = -1;
      list.append(button);
      return button;
    });
    select.after(wrapper);
    wrapper.append(select, trigger, list);
    select.classList.add('reference-native-select');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');
    const picker = { wrapper, trigger, list };
    pickers.push(picker);
    const open = (position = select.selectedIndex) => {
      pickers.forEach((other) => close(other));
      list.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
      options[Math.max(0, position)]?.focus();
    };
    trigger.addEventListener('click', () => list.hidden ? open() : close(picker));
    trigger.addEventListener('keydown', (event) => {
      if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
        event.preventDefault();
        open(event.key === 'ArrowUp' || event.key === 'End' ? options.length - 1 : 0);
      }
    });
    list.addEventListener('keydown', (event) => {
      const current = options.indexOf(document.activeElement);
      if (event.key === 'Escape') { event.preventDefault(); close(picker, true); }
      if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
        event.preventDefault();
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 :
          (current + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
        options[next].focus();
      }
    });
    options.forEach((button, optionIndex) => button.addEventListener('click', () => {
      select.selectedIndex = optionIndex;
      select.dispatchEvent(new Event('change', { bubbles: true }));
      value.textContent = button.textContent;
      trigger.setAttribute('aria-label', `${label}: ${button.textContent}`);
      options.forEach((other) => other.setAttribute('aria-selected', String(other === button)));
      close(picker, true);
    }));
    wrapper.addEventListener('focusout', (event) => {
      if (!wrapper.contains(event.relatedTarget)) close(picker);
    });
  });
  document.addEventListener('pointerdown', (event) => {
    pickers.forEach((picker) => { if (!picker.wrapper.contains(event.target)) close(picker); });
  });
  window.vpsReady?.('sel');
})();
