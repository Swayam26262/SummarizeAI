from django.utils.deprecation import MiddlewareMixin

class RemoveHopByHopHeadersMiddleware(MiddlewareMixin):
    def __call__(self, request):
        response = self.get_response(request)
        # Remove hop-by-hop headers
        hop_by_hop_headers = ['Connection', 'Keep-Alive', 'Proxy-Authenticate', 'Proxy-Authorization', 'TE', 'Trailers', 'Transfer-Encoding', 'Upgrade']
        for header in hop_by_hop_headers:
            if header in response:
                del response[header]
        return response 