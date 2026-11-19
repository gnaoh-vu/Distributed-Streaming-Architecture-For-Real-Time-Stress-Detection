function getTimelineSeconds(point, origin) {
    if (!state.dataBuffer.length || !point) return 0;
    return Math.max(0, Math.round(point.timestamp - origin));
}

function formatStatus(prediction) {
    if (!prediction || Number(prediction.label) < 0) {
	return { text: 'Waiting for prediction', className: 'pending', stress: null };
    }

    const stress = Number(prediction.label) === 1;

    return {
	text: stress ? 'STRESS DETECTED' : 'NORMAL',
	className: stress ? 'stress' : 'normal',
	stress
    };
}
