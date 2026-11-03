import { ArrowLeft } from 'lucide-react';
import Button from './Button';
import Modal from './Modal';

export default function TrainingDialog({ onClose }: { onClose: () => void }) {
  return <Modal title="Training" onClose={onClose}>
    <p>Your place to play, get feedback, and ask a chess trainer questions about the game. Training screens are coming next.</p>
    <Button onClick={onClose}><ArrowLeft size={18} aria-hidden="true" />Back to menu</Button>
  </Modal>;
}
