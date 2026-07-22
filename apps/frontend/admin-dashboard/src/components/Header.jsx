import { Bell, RefreshCw } from "lucide-react";
import { NotificationDropdown } from "./NotificationDropdown";

export function Header({ title, description, notifications, isOpen, setOpen, onRetry }) {
  const unread = notifications.filter((item) => item.unread).length;

  return (
    <header className="header">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="header-actions">
        <button className="icon-button" onClick={onRetry} aria-label="새로고침">
          <RefreshCw size={18} />
        </button>
        <div className="notification-wrap">
          <button className="icon-button" onClick={() => setOpen((value) => !value)} aria-label="알림">
            <Bell size={19} />
            {unread > 0 && <span className="badge-count">{unread}</span>}
          </button>
          {isOpen && <NotificationDropdown notifications={notifications} />}
        </div>
      </div>
    </header>
  );
}
