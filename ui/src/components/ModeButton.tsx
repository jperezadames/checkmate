import { ChevronRight, type LucideIcon } from 'lucide-react';

type ModeButtonProps = {
  title: string;
  description: string;
  icon: LucideIcon;
  tone?: 'green' | 'gold';
  disabled?: boolean;
  onClick?: () => void;
};

export default function ModeButton({ title, description, icon: Icon, tone = 'green', disabled = false, onClick }: ModeButtonProps) {
  return (
    <button type="button" className={`mode-button mode-button--${tone}`} disabled={disabled} onClick={onClick}>
      <span className="mode-icon"><Icon size={25} strokeWidth={1.7} aria-hidden="true" /></span>
      <span className="mode-copy"><span className="mode-title">{title}</span><span className="mode-description">{description}</span></span>
      {disabled ? <span className="mode-badge">Coming later</span> : <ChevronRight className="mode-arrow" size={22} aria-hidden="true" />}
    </button>
  );
}
