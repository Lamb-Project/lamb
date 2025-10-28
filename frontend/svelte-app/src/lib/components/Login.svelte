<script>
  import { createEventDispatcher } from 'svelte';
  import { user } from '$lib/stores/userStore';
  import { login } from '$lib/services/authService';
  import { goto } from '$app/navigation';
  import { base } from '$app/paths';
  import { _ , locale } from '$lib/i18n';
  import { onMount } from 'svelte';
  
  // Event dispatcher for component events
  const dispatch = createEventDispatcher();
  
  // Form state using $state
  let email = $state('');
  let password = $state('');
  let message = $state('');
  let success = $state(false);
  let loading = $state(false);
  
  let localeLoaded = $state(false);
  onMount(() => {
      const unsub = locale.subscribe(v => localeLoaded = !!v);
      return unsub;
  });
  
  // Handle form submission
  async function submitLogin() {
    loading = true;
    message = '';
    success = false;
    
    const result = await login(email, password);
    
    console.log('Login result:', result);
    console.log('User type:', result.data?.user_type);
    
    // Check the success flag and nested data object
    if (result.success && result.data) { 
      // Check if user is an end_user and redirect to OWI
      if (result.data.user_type === 'end_user') {
        console.log('End user detected! Redirecting to OWI...');
        success = true;
        message = 'Redirecting to Open WebUI...';
        
        // Redirect to OWI with the launch URL
        if (result.data.launch_url) {
          console.log('Redirecting to:', result.data.launch_url);
          window.location.href = result.data.launch_url;
        } else {
          // Fallback: show error if launch_url is missing
          console.error('No launch_url in response!');
          success = false;
          message = 'Unable to redirect to Open WebUI. Please contact your administrator.';
        }
        loading = false;
        return;
      }
      console.log('Creator user detected, continuing to creator interface');
      
      // For creator users, continue with normal login
      user.login(result.data); 
      
      success = true;
      message = 'Login successful!'; // Use a generic message or i18n key
      
      setTimeout(() => {
        goto(base + '/', { replaceState: true });
      }, 1000);
    } else {
      // Handle login failure
      success = false;
      message = result.error || 'Login failed. Please check credentials.'; // Provide a clearer default error
    }
    
    loading = false;
  }
  
  // Show signup form
  function showSignup() {
    dispatch('show-signup');
  }
</script>

<div class="max-w-md mx-auto bg-white shadow-md rounded-lg overflow-hidden">
  <div class="p-6">
    <h2 class="text-2xl font-bold mb-6">{localeLoaded ? $_('auth.loginTitle') : 'Login'}</h2>
    <form onsubmit={submitLogin} class="space-y-4">
      <div class="space-y-2">
        <label for="email" class="block text-sm font-medium">{localeLoaded ? $_('auth.email') : 'Email'}</label>
        <input 
          type="email" 
          id="email" 
          bind:value={email} 
          required
          class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand"
        />
      </div>
      
      <div class="space-y-2">
        <label for="password" class="block text-sm font-medium">{localeLoaded ? $_('auth.password') : 'Password'}</label>
        <input 
          type="password" 
          id="password" 
          bind:value={password} 
          required
          class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-brand focus:border-brand"
        />
      </div>
      
      {#if message}
        <div class={`p-3 rounded-md ${success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
          {message}
        </div>
      {/if}
      
      <button 
        type="submit" 
        disabled={loading}
        class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-brand hover:bg-brand-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand disabled:opacity-50"
      >
        {#if loading}
          <span>{localeLoaded ? $_('auth.loading') : 'Loading...'}</span>
        {:else}
          <span>{localeLoaded ? $_('auth.loginButton') : 'Login'}</span>
        {/if}
      </button>
      
      <div class="text-center mt-4">
        <p class="text-sm text-gray-600">
          {localeLoaded ? $_('auth.noAccount') : "Don't have an account?"}
          <button 
            type="button" 
            onclick={showSignup} 
            class="text-brand hover:text-brand-hover font-medium"
          >
            {localeLoaded ? $_('auth.signupLink') : 'Sign up'}
          </button>
        </p>
      </div>
    </form>
  </div>
</div> 