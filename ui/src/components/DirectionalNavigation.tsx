import { useLayoutEffect, useRef, type ReactNode } from 'react';

const STEPS: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1 };
const TARGETS = 'button, input, select, textarea, a[href], [tabindex]';

function targetsIn(scope: HTMLElement): HTMLElement[] {
  return Array.from(scope.querySelectorAll<HTMLElement>(TARGETS)).filter(element => {
    const rect = element.getBoundingClientRect();
    return element.tabIndex >= 0 && !element.matches(':disabled, [aria-disabled="true"]')
      && !element.closest('[hidden], [inert], [aria-hidden="true"]')
      && rect.width > 0 && rect.height > 0 && getComputedStyle(element).visibility !== 'hidden';
  });
}

function activeScope(root: HTMLElement): HTMLElement {
  return document.querySelector<HTMLDialogElement>('dialog[data-nav-scope][open]') ?? root;
}

function focusTarget(target: HTMLElement) {
  target.focus({ preventScroll: true });
  target.scrollIntoView({ block: 'nearest', inline: 'nearest' });
}

function firstTarget(scope: HTMLElement): HTMLElement | undefined {
  const targets = targetsIn(scope);
  return targets.find(element => element.hasAttribute('data-nav-initial')) ?? targets[0];
}

/** Rotary turns arrive as Left/Right and cycle through controls in DOM order, wrapping at each end.
 * Select arrives as Enter. Laptop preview controls keep normal browser keys. */
export default function DirectionalNavigation({ children, focusKey }: { children: ReactNode; focusKey: string }) {
  const root = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const element = root.current;
    if (!element) return;
    const scope = activeScope(element);
    const current = document.activeElement;
    // Do not steal focus from a developer's preview selector or another text field.
    if (current && current !== document.body && !element.contains(current) && !scope.contains(current)) return;
    const target = firstTarget(scope);
    if (target) focusTarget(target);
  }, [focusKey]);

  useLayoutEffect(() => {
    const element = root.current;
    if (!element) return;
    let pendingFrame = 0;

    function recoverFocus() {
      const scope = activeScope(element!);
      const current = document.activeElement;
      if (current && current !== document.body && !element!.contains(current) && !scope.contains(current)) return;
      if (!current || !targetsIn(scope).includes(current as HTMLElement)) {
        const target = firstTarget(scope);
        if (target) focusTarget(target);
      }
    }

    function handleKey(event: KeyboardEvent) {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const step = STEPS[event.key];
      if (!step && event.key !== 'Enter') return;
      const scope = activeScope(element!);
      const current = document.activeElement;
      if (current && current !== document.body && !scope.contains(current)) return;
      if (current instanceof HTMLElement && (current.isContentEditable || current.matches('textarea, select, input:not([type="checkbox"]):not([type="radio"]):not([type="button"]):not([type="submit"])'))) return;

      const targets = targetsIn(scope);
      const focused = targets.find(target => target === current);
      event.preventDefault();
      if (!focused) {
        const target = firstTarget(scope);
        if (target) focusTarget(target);
        return; // Recover the highlight without accidentally activating an action.
      }
      if (step) {
        const index = (targets.indexOf(focused) + step + targets.length) % targets.length;
        focusTarget(targets[index]);
      } else if (!event.repeat) {
        focused.click(); // Includes checkboxes: Enter normally doesn't toggle them.
      }
    }

    const observer = new MutationObserver(() => {
      cancelAnimationFrame(pendingFrame);
      pendingFrame = requestAnimationFrame(recoverFocus);
    });
    observer.observe(element, { subtree: true, childList: true, attributes: true, attributeFilter: ['disabled', 'hidden', 'open'] });
    document.addEventListener('keydown', handleKey);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(pendingFrame);
      document.removeEventListener('keydown', handleKey);
    };
  }, []);

  return <div className="directional-navigation" data-nav-scope ref={root}>{children}</div>;
}
