import React from 'react';
import './PlayerAvatar.css';

const PlayerAvatar = ({ name, image, size = 'md', className = '' }) => {
  const getInitials = (name) => {
    if (!name) return '?';
    return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
  };

  const initials = getInitials(name);
  
  return (
    <div className={`player-avatar-container avatar-${size} ${className}`}>
      {image ? (
        <img src={image} alt={name} className="avatar-image" />
      ) : (
        <div className="avatar-initials">{initials}</div>
      )}
    </div>
  );
};

export default PlayerAvatar;
