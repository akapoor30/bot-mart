import React from 'react';
import { ExternalLink, Tag } from 'lucide-react';

const ProductCard = ({ data, platform }) => {
    const isCheapest = data.is_cheapest;

    return (
        <div className={`product-card ${isCheapest ? 'border-2 border-green-500' : ''}`}>
            {isCheapest && <span className="badge">Best Deal</span>}
            <img src={data.image} alt={data.title} />
            <h3>{data.title}</h3>
            <div className="price-row">
                <Tag size={16} />
                <span>₹{data.price}</span>
                <span className="platform-name">{platform}</span>
            </div>
            <a href={data.link} target="_blank" rel="noreferrer">
                View on {platform} <ExternalLink size={14} />
            </a>
        </div>
    );
};

// THIS LINE IS CRUCIAL
export default ProductCard;