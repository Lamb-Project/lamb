<script>import { twMerge } from "tailwind-merge";
export let review;
export let articleClass = "md:gap-8 md:grid md:grid-cols-3";
export let divClass = "flex items-center mb-6 space-x-4 rtl:space-x-reverse";
export let imgClass = "w-10 h-10 rounded-full";
export let ulClass = "space-y-4 text-sm text-gray-500 dark:text-gray-400";
export let liClass = "flex items-center";
export let classArticle = "";
export let classDiv = "";
export let classImg = "";
export let classUl = "";
export let classLi = "";
</script>

<article class={twMerge(articleClass, classArticle)}>
  <div>
    <div class={twMerge(divClass, classDiv)}>
      <img class={twMerge(imgClass, classImg)} src={review.imgSrc} alt={review.imgAlt} />
      <div class="space-y-1 font-medium dark:text-white">
        <p>{review.name}</p>
        {#if review.address}
          <div class="flex items-center text-sm text-gray-500 dark:text-gray-400">
            <slot name="address" />
          </div>
        {/if}
      </div>
    </div>
    {#if $$slots.item1 || $$slots.item2 || $$slots.item3}
      <ul class={twMerge(ulClass, classUl)}>
        {#if $$slots.item1}
          <li class={twMerge(liClass, classLi)}>
            <slot name="item1" />
          </li>
        {/if}
        {#if $$slots.item2}
          <li class={twMerge(liClass, classLi)}>
            <slot name="item2" />
          </li>
        {/if}
        {#if $$slots.item3}
          <li class={twMerge(liClass, classLi)}>
            <slot name="item3" />
          </li>
        {/if}
      </ul>
    {/if}
  </div>
  <div class="col-span-2 mt-6 md:mt-0">
    <div class="flex items-start mb-5">
      <div class="pe-4">
        {#if review.reviewDate}
          <footer>
            <p class="mb-2 text-sm text-gray-500 dark:text-gray-400">
              Reviewed: {review.reviewDate}
            </p>
          </footer>
        {/if}
        <h4 class="text-xl font-bold text-gray-900 dark:text-white">
          {review.title}
        </h4>
      </div>
      <p class="bg-primary-700 text-white text-sm font-semibold inline-flex items-center p-1.5 rounded-sm">
        {review.rating}
      </p>
    </div>
    <slot />
  </div>
</article>

<!--
@component
[Go to docs](https://flowbite-svelte.com/)
## Props
@prop export let review: $$Props['review'];
@prop export let articleClass: $$Props['articleClass'] = 'md:gap-8 md:grid md:grid-cols-3';
@prop export let divClass: $$Props['divClass'] = 'flex items-center mb-6 space-x-4 rtl:space-x-reverse';
@prop export let imgClass: $$Props['imgClass'] = 'w-10 h-10 rounded-full';
@prop export let ulClass: $$Props['ulClass'] = 'space-y-4 text-sm text-gray-500 dark:text-gray-400';
@prop export let liClass: $$Props['liClass'] = 'flex items-center';
@prop export let classArticle: $$Props['classArticle'] = '';
@prop export let classDiv: $$Props['classDiv'] = '';
@prop export let classImg: $$Props['classImg'] = '';
@prop export let classUl: $$Props['classUl'] = '';
@prop export let classLi: $$Props['classLi'] = '';
-->
