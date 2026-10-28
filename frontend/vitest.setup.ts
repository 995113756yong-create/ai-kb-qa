import "@testing-library/jest-dom/vitest";

// jsdom 没有实现这两个布局相关 API，组件里用到时补一个空实现
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
