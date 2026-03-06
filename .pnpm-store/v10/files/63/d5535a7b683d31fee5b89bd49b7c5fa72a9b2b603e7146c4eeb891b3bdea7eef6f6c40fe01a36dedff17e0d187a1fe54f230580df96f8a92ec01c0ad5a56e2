export const canChangeSlide = ({ lastSlideChange, slideDuration, slideDurationRatio = 1 }) => {
    if (lastSlideChange && new Date().getTime() - lastSlideChange.getTime() < slideDuration * slideDurationRatio) {
        console.warn("Can't change slide yet, too soon");
        return false;
    }
    return true;
};
