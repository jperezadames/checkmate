import { useLayoutEffect, useRef, type ReactNode } from 'react';
import { angleIndex } from '../navigation/angle';
import type { ControlInput } from '../types/game';

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

/** The bounded Pico dial maps its angle across enabled controls; Select uses the Enter path.
 * Laptop Left/Right keys cycle through controls, wrapping at each end. */
export default function DirectionalNavigation({ children, focusKey }: { children: ReactNode; focusKey: string }) {
  const root = useRef<HTMLDivElement>(null);
  const lastPosition = useRef<number | null>(null);

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

    function handlePicoInput(event: Event) {
      const input = (event as CustomEvent<ControlInput>).detail;
      if (!Number.isFinite(input.position) || input.position < 0 || input.position > 1) return;
      const scope = activeScope(element!);
      const targets = targetsIn(scope);
      const current = document.activeElement as HTMLElement | null;
      if (input.position !== lastPosition.current) {
        lastPosition.current = input.position;
        if (current?.matches('[data-nav-scroll="true"]')) {
          current.scrollTop = input.position * (current.scrollHeight - current.clientHeight);
        } else {
          const index = angleIndex(input.position, targets.length, targets.indexOf(current!));
          if (index >= 0 && targets[index] !== current) focusTarget(targets[index]);
        }
      }
      if (input.select) {
        const target = document.activeElement as HTMLElement | null;
        if (target && targets.includes(target)) {
          // Dispatch through the existing Enter path, including move-history browsing.
          target.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
        } else {
          const initial = firstTarget(scope);
          if (initial) focusTarget(initial);
        }
      }
    }

    const observer = new MutationObserver(() => {
      cancelAnimationFrame(pendingFrame);
      pendingFrame = requestAnimationFrame(recoverFocus);
    });
    observer.observe(element, { subtree: true, childList: true, attributes: true, attributeFilter: ['disabled', 'hidden', 'open'] });
    document.addEventListener('keydown', handleKey);
    document.addEventListener('checkmate-input', handlePicoInput);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(pendingFrame);
      document.removeEventListener('keydown', handleKey);
      document.removeEventListener('checkmate-input', handlePicoInput);
    };
  }, []);

  return <div className="directional-navigation" data-nav-scope ref={root}>{children}</div>;
}
